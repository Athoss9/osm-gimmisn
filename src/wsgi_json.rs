/*
 * Copyright 2021 Miklos Vajna. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#![deny(warnings)]
#![warn(clippy::all)]
#![warn(missing_docs)]

//! Contains functionality specific to the json part of the web interface.

use crate::areas;
use crate::context;
use crate::overpass_query;
use crate::webframe;
use anyhow::Context;
use std::collections::HashMap;

/// Expected request_uri: e.g. /osm/streets/ormezo/update-result.json.
fn streets_update_result_json(
    ctx: &context::Context,
    relations: &mut areas::Relations,
    request_uri: &str,
) -> anyhow::Result<String> {
    let mut tokens = request_uri.split('/');
    tokens.next_back();
    let relation_name = tokens.next_back().unwrap();
    let relation = relations
        .get_relation(relation_name)
        .context("get_relation() failed")?;
    let query = relation.get_osm_streets_query()?;
    let mut ret: HashMap<String, String> = HashMap::new();
    match overpass_query::overpass_query(ctx, query) {
        Ok(buf) => {
            relation.get_files().write_osm_streets(ctx, &buf)?;
            ret.insert("error".into(), "".into())
        }
        Err(err) => ret.insert("error".into(), err.to_string()),
    };
    Ok(serde_json::to_string(&ret)?)
}

/// Expected request_uri: e.g. /osm/street-housenumbers/ormezo/update-result.json.
fn street_housenumbers_update_result_json(
    ctx: &context::Context,
    relations: &mut areas::Relations,
    request_uri: &str,
) -> anyhow::Result<String> {
    let mut tokens = request_uri.split('/');
    tokens.next_back();
    let relation_name = tokens.next_back().unwrap();
    let relation = relations.get_relation(relation_name)?;
    let query = relation.get_osm_housenumbers_query()?;
    let mut ret: HashMap<String, String> = HashMap::new();
    match overpass_query::overpass_query(ctx, query) {
        Ok(buf) => {
            relation.get_files().write_osm_housenumbers(ctx, &buf)?;
            ret.insert("error".into(), "".into())
        }
        Err(err) => ret.insert("error".into(), err.to_string()),
    };
    Ok(serde_json::to_string(&ret)?)
}

/// Expected request_uri: e.g. /osm/missing-housenumbers/ormezo/update-result.json.
fn missing_housenumbers_update_result_json(
    ctx: &context::Context,
    relations: &mut areas::Relations,
    request_uri: &str,
) -> anyhow::Result<String> {
    let mut tokens = request_uri.split('/');
    tokens.next_back();
    let relation_name = tokens.next_back().unwrap();
    let references = ctx.get_ini().get_reference_housenumber_paths()?;
    let relation = relations.get_relation(relation_name)?;
    let mut ret: HashMap<String, String> = HashMap::new();
    match relation.write_ref_housenumbers(&references) {
        Ok(_) => ret.insert("error".into(), "".into()),
        Err(err) => ret.insert("error".into(), err.to_string()),
    };
    Ok(serde_json::to_string(&ret)?)
}

/// Expected request_uri: e.g. /osm/missing-streets/ormezo/update-result.json.
fn missing_streets_update_result_json(
    ctx: &context::Context,
    relations: &mut areas::Relations,
    request_uri: &str,
) -> anyhow::Result<String> {
    let mut tokens = request_uri.split('/');
    tokens.next_back();
    let relation_name = tokens.next_back().unwrap();
    let reference = ctx.get_ini().get_reference_street_path()?;
    let relation = relations.get_relation(relation_name)?;
    let mut ret: HashMap<String, String> = HashMap::new();
    match relation.write_ref_streets(&reference) {
        Ok(_) => ret.insert("error".into(), "".into()),
        Err(err) => ret.insert("error".into(), err.to_string()),
    };
    Ok(serde_json::to_string(&ret)?)
}

/// Dispatches json requests based on their URIs.
pub fn our_application_json(
    environ: &HashMap<String, String>,
    ctx: &context::Context,
    relations: &mut areas::Relations,
    request_uri: &str,
) -> anyhow::Result<(String, webframe::Headers, Vec<u8>)> {
    let content_type = "application/json";
    let headers: webframe::Headers = Vec::new();
    let prefix = ctx.get_ini().get_uri_prefix()?;
    let output: String;
    if request_uri.starts_with(&format!("{}/streets/", prefix)) {
        output = streets_update_result_json(ctx, relations, request_uri)?;
    } else if request_uri.starts_with(&format!("{}/street-housenumbers/", prefix)) {
        output = street_housenumbers_update_result_json(ctx, relations, request_uri)?;
    } else if request_uri.starts_with(&format!("{}/missing-housenumbers/", prefix)) {
        output = missing_housenumbers_update_result_json(ctx, relations, request_uri)?;
    } else {
        // Assume that request_uri starts with prefix + "/missing-streets/".
        output = missing_streets_update_result_json(ctx, relations, request_uri)?;
    }
    let output_bytes = output.as_bytes();
    let response = webframe::Response::new(content_type, "200 OK", output_bytes, &headers);
    webframe::compress_response(environ, &response)
}