/*
 * Copyright 2021 Miklos Vajna. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#![deny(warnings)]
#![warn(clippy::all)]
#![warn(missing_docs)]

//! The cache_yamls module caches YAML files from the data/ directory.

use crate::areas;
use crate::context;
use anyhow::Context;
use std::collections::HashMap;
use std::ops::DerefMut;

/// Commandline interface.
pub fn main(argv: &[String], ctx: &context::Context) -> anyhow::Result<()> {
    let mut cache: HashMap<String, serde_json::Value> = HashMap::new();
    let datadir = ctx.get_abspath(&argv[1]);
    let entries =
        std::fs::read_dir(&datadir).context(format!("failed to read_dir() {}", datadir))?;
    let mut yaml_paths: Vec<String> = Vec::new();
    for entry in entries {
        let path = entry?.path();
        let path = path.to_str().context("failed to convert path to string")?;
        if path.ends_with(".yaml") {
            yaml_paths.push(path.to_string());
        }
    }
    yaml_paths.sort();
    for yaml_path in yaml_paths {
        let cache_key = yaml_path
            .strip_prefix(&format!("{}/", datadir))
            .context("yaml outside datadir")?
            .to_string();
        let data = ctx.get_file_system().read_to_string(&yaml_path)?;
        let cache_value = serde_yaml::from_str::<serde_json::Value>(&data)
            .context(format!("serde_yaml::from_str() failed for {}", yaml_path))?;
        cache.insert(cache_key, cache_value);
    }

    let cache_path = format!("{}/yamls.cache", datadir);
    {
        let write_stream = ctx.get_file_system().open_write(&cache_path)?;
        let mut guard = write_stream.borrow_mut();
        let write = guard.deref_mut();
        serde_json::to_writer(write, &cache)?;
    }

    let workdir = ctx.get_abspath(&argv[2]);
    let yaml_path = format!("{}/relations.yaml", datadir);
    let mut relation_ids: Vec<u64> = Vec::new();
    let stream = std::fs::File::open(yaml_path)?;
    let relations: areas::RelationsDict = serde_yaml::from_reader(stream)?;
    for (_key, value) in relations {
        relation_ids.push(value.osmrelation.context("no osmrelation")?);
    }
    relation_ids.sort_unstable();
    relation_ids.dedup();
    let statsdir = format!("{}/stats", workdir);
    std::fs::create_dir_all(&statsdir)?;
    {
        let write_stream = ctx
            .get_file_system()
            .open_write(&format!("{}/relations.json", statsdir))?;
        let mut guard = write_stream.borrow_mut();
        let write = guard.deref_mut();
        serde_json::to_writer(write, &relation_ids)?;
    }

    Ok(())
}

#[cfg(test)]
mod tests;
