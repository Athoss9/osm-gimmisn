#!/usr/bin/env python3
#
# Copyright (c) 2019 Miklos Vajna and contributors.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The test_areas module covers the areas module."""

from typing import Any
from typing import Dict
from typing import List
import io
import json
import os
import unittest

import test_context

import areas
import rust
import util
import yattag


class TestRelationFilesWriteOsmStreets(unittest.TestCase):
    """Tests RelationFiles.write_osm_streets()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        ctx = test_context.make_test_context()
        relations = areas.make_relations(ctx)
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        result_from_overpass = "@id\tname\n1\tTűzkő utca\n2\tTörökugrató utca\n3\tOSM Name 1\n4\tHamzsabégi út\n"
        expected = util.get_content(relations.get_workdir() + "/streets-gazdagret.csv")
        file_system = test_context.TestFileSystem()
        streets_value = io.BytesIO()
        streets_value.__setattr__("close", lambda: None)
        files = {
            ctx.get_abspath("workdir/streets-gazdagret.csv"): streets_value,
        }
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        relation.get_files().write_osm_streets(ctx, result_from_overpass)
        streets_value.seek(0)
        self.assertEqual(streets_value.read(), expected)


class TestRelationFilesWriteOsmHousenumbers(unittest.TestCase):
    """Tests RelationFiles.write_osm_housenumbers()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        ctx = test_context.make_test_context()
        relations = areas.make_relations(ctx)
        relation_name = "gazdagret"
        result_from_overpass = "@id\taddr:street\taddr:housenumber\taddr:postcode\taddr:housename\t"
        result_from_overpass += "addr:conscriptionnumber\taddr:flats\taddr:floor\taddr:door\taddr:unit\tname\t@type\n\n"
        result_from_overpass += "1\tTörökugrató utca\t1\t\t\t\t\t\t\t\t\tnode\n"
        result_from_overpass += "1\tTörökugrató utca\t2\t\t\t\t\t\t\t\t\tnode\n"
        result_from_overpass += "1\tTűzkő utca\t9\t\t\t\t\t\t\t\t\tnode\n"
        result_from_overpass += "1\tTűzkő utca\t10\t\t\t\t\t\t\t\t\tnode\n"
        result_from_overpass += "1\tOSM Name 1\t1\t\t\t\t\t\t\t\t\tnode\n"
        result_from_overpass += "1\tOSM Name 1\t2\t\t\t\t\t\t\t\t\tnode\n"
        result_from_overpass += "1\tOnly In OSM utca\t1\t\t\t\t\t\t\t\t\tnode\n"
        result_from_overpass += "1\tSecond Only In OSM utca\t1\t\t\t\t\t\t\t\t\tnode\n"
        expected = util.get_content(relations.get_workdir() + "/street-housenumbers-gazdagret.csv")
        relation = relations.get_relation(relation_name)
        file_system = test_context.TestFileSystem()
        housenumbers_value = io.BytesIO()
        housenumbers_value.__setattr__("close", lambda: None)
        files = {
            ctx.get_abspath("workdir/street-housenumbers-gazdagret.csv"): housenumbers_value,
        }
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        relation.get_files().write_osm_housenumbers(ctx, result_from_overpass)
        housenumbers_value.seek(0)
        self.assertEqual(housenumbers_value.read(), expected)


def make_range(start: int, end: int) -> rust.PyRange:
    """Factory for Range without specifying interpolation."""
    return rust.PyRange(start, end, interpolation="")


def get_filters(relation: rust.PyRelation) -> Dict[str, Any]:
    """Wrapper around get_config.get_filters() that doesn't return an Optional."""
    filters_str = relation.get_config().get_filters()
    filters: Dict[str, Any] = {}
    if filters_str:
        filters = json.loads(filters_str)
    return filters


class TestRelationGetStreetRanges(unittest.TestCase):
    """Tests Relation.get_street_ranges()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation("gazdagret")
        filters = relation.get_street_ranges()
        expected_filters = {
            "Budaörsi út": rust.PyRanges([make_range(137, 165)]),
            "Csiki-hegyek utca": rust.PyRanges([make_range(1, 15), make_range(2, 26)]),
            'Hamzsabégi út': rust.PyRanges([rust.PyRange(start=1, end=12, interpolation="all")])
        }
        self.assertEqual(filters, expected_filters)
        expected_streets = {
            'OSM Name 1': 'Ref Name 1',
            'OSM Name 2': 'Ref Name 2',
            'Misspelled OSM Name 1': 'OSM Name 1',
        }
        relations = areas.make_relations(test_context.make_test_context())
        self.assertEqual(relations.get_relation("gazdagret").get_config().get_refstreets(), expected_streets)
        street_blacklist = relations.get_relation("gazdagret").get_config().get_street_filters()
        self.assertEqual(street_blacklist, ['Only In Ref Nonsense utca'])

    def test_empty(self) -> None:
        """Tests when the filter file is empty."""
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation("empty")
        filters = relation.get_street_ranges()
        self.assertEqual(filters, {})


class TestRelationGetRefStreetFromOsmStreet(unittest.TestCase):
    """Tests Relation.get_ref_street_from_osm_street()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relations = areas.make_relations(test_context.make_test_context())
        street = "Budaörsi út"
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        refcounty = relation.get_config().get_refcounty()
        street = relation.get_config().get_ref_street_from_osm_street(street)
        self.assertEqual("01", refcounty)
        self.assertEqual(["011"], relation.get_config().get_street_refsettlement(street))
        self.assertEqual("Budaörsi út", street)

    def test_refsettlement_override(self) -> None:
        """Tests street-specific refsettlement override."""
        relations = areas.make_relations(test_context.make_test_context())
        street = "Teszt utca"
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        refcounty = relation.get_config().get_refcounty()
        street = relation.get_config().get_ref_street_from_osm_street(street)
        self.assertEqual("01", refcounty)
        self.assertEqual(["012"], relation.get_config().get_street_refsettlement(street))
        self.assertEqual("Teszt utca", street)

    def test_refstreets(self) -> None:
        """Tests OSM -> ref name mapping."""
        relations = areas.make_relations(test_context.make_test_context())
        street = "OSM Name 1"
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        refcounty = relation.get_config().get_refcounty()
        street = relation.get_config().get_ref_street_from_osm_street(street)
        self.assertEqual("01", refcounty)
        self.assertEqual(["011"], relation.get_config().get_street_refsettlement(street))
        self.assertEqual("Ref Name 1", street)

    def test_nosuchrelation(self) -> None:
        """Tests a relation without a filter file."""
        relations = areas.make_relations(test_context.make_test_context())
        street = "OSM Name 1"
        relation_name = "nosuchrelation"
        relation = relations.get_relation(relation_name)
        refcounty = relation.get_config().get_refcounty()
        street = relation.get_config().get_ref_street_from_osm_street(street)
        self.assertEqual("01", refcounty)
        self.assertEqual(["011"], relation.get_config().get_street_refsettlement(street))
        self.assertEqual("OSM Name 1", street)

    def test_emptyrelation(self) -> None:
        """Tests a relation with an empty filter file."""
        relations = areas.make_relations(test_context.make_test_context())
        street = "OSM Name 1"
        relation_name = "empty"
        relation = relations.get_relation(relation_name)
        refcounty = relation.get_config().get_refcounty()
        street = relation.get_config().get_ref_street_from_osm_street(street)
        self.assertEqual("01", refcounty)
        self.assertEqual(["011"], relation.get_config().get_street_refsettlement(street))
        self.assertEqual("OSM Name 1", street)

    def test_range_level_override(self) -> None:
        """Tests the refsettlement range-level override."""
        relations = areas.make_relations(test_context.make_test_context())
        street = "Csiki-hegyek utca"
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        refcounty = relation.get_config().get_refcounty()
        street = relation.get_config().get_ref_street_from_osm_street(street)
        self.assertEqual("01", refcounty)
        self.assertEqual(["011", "013"], relation.get_config().get_street_refsettlement(street))
        self.assertEqual("Csiki-hegyek utca", street)


class TestRelationGetRefStreets(unittest.TestCase):
    """Tests Relation.GetRefStreets()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relation_name = "gazdagret"
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation(relation_name)
        house_numbers = relation.get_ref_streets()
        self.assertEqual(house_numbers, ['Hamzsabégi út',
                                         'Only In Ref Nonsense utca',
                                         'Only In Ref utca',
                                         'Ref Name 1',
                                         'Törökugrató utca',
                                         'Tűzkő utca'])


class TestRelationGetOsmHouseNumbers(unittest.TestCase):
    """Tests Relation.get_osm_housenumbers()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relation_name = "gazdagret"
        street_name = "Törökugrató utca"
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation(relation_name)
        house_numbers = relation.get_osm_housenumbers(street_name)
        self.assertEqual([i.get_number() for i in house_numbers], ["1", "2"])

    def test_addr_place(self) -> None:
        """Tests the case when addr:place is used instead of addr:street."""
        relation_name = "gh964"
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation(relation_name)
        street_name = "Tolvajos tanya"
        house_numbers = relation.get_osm_housenumbers(street_name)
        self.assertEqual([i.get_number() for i in house_numbers], ["52"])


class TestRelationGetMissingHousenumbers(unittest.TestCase):
    """Tests Relation.get_missing_housenumbers()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relations = areas.make_relations(test_context.make_test_context())
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        ongoing_streets, done_streets = relation.get_missing_housenumbers()
        ongoing_streets_strs = [(name.get_osm_name(), [i.get_number()
                                                       for i in numbers]) for name, numbers in ongoing_streets]
        # Notice how 11 and 12 is filtered out by the 'invalid' mechanism for 'Törökugrató utca'.
        self.assertEqual(ongoing_streets_strs, [('Törökugrató utca', ['7', '10']),
                                                ('Tűzkő utca', ['1', '2']),
                                                ('Hamzsabégi út', ['1'])])
        expected = [('OSM Name 1', ['1', '2']), ('Törökugrató utca', ['1', '2']), ('Tűzkő utca', ['9', '10'])]
        done_streets_strs = [(name.get_osm_name(), [i.get_number()
                                                    for i in numbers]) for name, numbers in done_streets]
        self.assertEqual(done_streets_strs, expected)

    def test_letter_suffix(self) -> None:
        """Tests that 7/A is detected when 7/B is already mapped."""
        relations = areas.make_relations(test_context.make_test_context())
        relation_name = "gh267"
        relation = relations.get_relation(relation_name)
        # Opt-in, this is not the default behavior.
        config = relation.get_config()
        config.set_housenumber_letters(True)
        relation.set_config(config)
        ongoing_streets, _done_streets = relation.get_missing_housenumbers()
        ongoing_street = ongoing_streets[0]
        housenumber_ranges = util.get_housenumber_ranges(ongoing_street[1])
        housenumber_range_names = [i.get_number() for i in housenumber_ranges]
        housenumber_range_names = sorted(housenumber_range_names, key=util.split_house_number)
        # Make sure that 1/1 shows up in the output: it's not the same as '1' or '11'.
        expected = ['1', '1/1', '1/2', '3', '5', '7', '7/A', '7/B', '7/C', '9', '11', '13', '13-15']
        self.assertEqual(housenumber_range_names, expected)

    def test_letter_suffix_invalid(self) -> None:
        """Tests how 'invalid' interacts with normalization."""
        relations = areas.make_relations(test_context.make_test_context())
        relation_name = "gh296"
        relation = relations.get_relation(relation_name)
        # Opt-in, this is not the default behavior.
        config = relation.get_config()
        config.set_housenumber_letters(True)
        # Set custom 'invalid' map.
        filters = {
            "Rétköz utca": {
                "invalid": ["9", "47"]
            }
        }
        config.set_filters(json.dumps(filters))
        relation.set_config(config)
        ongoing_streets, _done_streets = relation.get_missing_housenumbers()
        ongoing_street = ongoing_streets[0]
        housenumber_ranges = util.get_housenumber_ranges(ongoing_street[1])
        housenumber_range_names = [i.get_number() for i in housenumber_ranges]
        housenumber_range_names = sorted(housenumber_range_names, key=util.split_house_number)
        # Notice how '9 A 1' is missing here: it's not a simple house number, so it gets normalized
        # to just '9' and the above filter silences it.
        expected = ['9/A']
        self.assertEqual(housenumber_range_names, expected)

    def test_invalid_simplify(self) -> None:
        """Tests how 'invalid' interacts with housenumber-letters: true or false."""
        relations = areas.make_relations(test_context.make_test_context())
        relation_name = "gh385"
        relation = relations.get_relation(relation_name)

        # Default case: housenumber-letters=false.
        filters: Dict[str, Any] = {
            "Kővirág sor": {
                "invalid": ["37b"]
            }
        }
        config = relation.get_config()
        config.set_filters(json.dumps(filters))
        relation.set_config(config)
        ongoing_streets, _done_streets = relation.get_missing_housenumbers()
        # Note how 37b from invalid is simplified to 37; and how 37/B from ref is simplified to
        # 37 as well, so we find the match.
        self.assertFalse(len(ongoing_streets))

        # Opt-in case: housenumber-letters=true.
        config = relation.get_config()
        config.set_housenumber_letters(True)
        relation.set_config(config)
        filters = {
            "Kővirág sor": {
                "invalid": ["37b"]
            }
        }
        config = relation.get_config()
        config.set_filters(json.dumps(filters))
        relation.set_config(config)
        ongoing_streets, _done_streets = relation.get_missing_housenumbers()
        # In this case 37b from invalid matches 37/B from ref.
        self.assertFalse(len(ongoing_streets))

        # Make sure out-of-range invalid elements are just ignored and no exception is raised.
        config = relation.get_config()
        config.set_housenumber_letters(False)
        relation.set_config(config)
        filters = {
            "Kővirág sor": {
                "invalid": ["5"],
                "ranges": [{"start": "1", "end": "3"}],
            }
        }
        config = relation.get_config()
        config.set_filters(json.dumps(filters))
        relation.set_config(config)
        relation.get_missing_housenumbers()

    def test_letter_suffix_normalize(self) -> None:
        """Tests that '42 A' vs '42/A' is recognized as a match."""
        relations = areas.make_relations(test_context.make_test_context())
        relation_name = "gh286"
        relation = relations.get_relation(relation_name)
        # Opt-in, this is not the default behavior.
        config = relation.get_config()
        config.set_housenumber_letters(True)
        relation.set_config(config)
        ongoing_streets, _done_streets = relation.get_missing_housenumbers()
        ongoing_street = ongoing_streets[0]
        housenumber_ranges = util.get_housenumber_ranges(ongoing_street[1])
        housenumber_range_names = [i.get_number() for i in housenumber_ranges]
        housenumber_range_names = sorted(housenumber_range_names, key=util.split_house_number)
        # Note how 10/B is not in this list.
        expected = ['10/A']
        self.assertEqual(housenumber_range_names, expected)

    def test_letter_suffix_source_suffix(self) -> None:
        """Tests that '42/A*' and '42/a' matches."""
        relations = areas.make_relations(test_context.make_test_context())
        relation_name = "gh299"
        relation = relations.get_relation(relation_name)
        # Opt-in, this is not the default behavior.
        config = relation.get_config()
        config.set_housenumber_letters(True)
        relation.set_config(config)
        ongoing_streets, _done_streets = relation.get_missing_housenumbers()
        # Note how '52/B*' is not in this list.
        self.assertEqual(ongoing_streets, [])

    def test_letter_suffix_normalize_semicolon(self) -> None:
        """Tests that 'a' is not stripped from '1;3a'."""
        relations = areas.make_relations(test_context.make_test_context())
        relation_name = "gh303"
        relation = relations.get_relation(relation_name)
        # Opt-in, this is not the default behavior.
        config = relation.get_config()
        config.set_housenumber_letters(True)
        relation.set_config(config)
        ongoing_streets, _done_streets = relation.get_missing_housenumbers()
        ongoing_street = ongoing_streets[0]
        housenumber_ranges = util.get_housenumber_ranges(ongoing_street[1])
        housenumber_range_names = [i.get_number() for i in housenumber_ranges]
        housenumber_range_names = sorted(housenumber_range_names, key=util.split_house_number)
        # Note how 43/B and 43/C is not here.
        expected = ['43/A', '43/D']
        self.assertEqual(housenumber_range_names, expected)


class TestRelationGetMissingStreets(unittest.TestCase):
    """Tests Relation.get_missing_streets()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relations = areas.make_relations(test_context.make_test_context())
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        only_in_reference, in_both = relation.get_missing_streets()

        # Note that 'Only In Ref Nonsense utca' is missing from this list.
        self.assertEqual(only_in_reference, ['Only In Ref utca'])

        self.assertEqual(in_both, ['Hamzsabégi út', 'Ref Name 1', 'Törökugrató utca', 'Tűzkő utca'])


class TestRelationGetAdditionalStreets(unittest.TestCase):
    """Tests Relation.get_additional_streets()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relations = areas.make_relations(test_context.make_test_context())
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        only_in_osm = relation.get_additional_streets(sorted_result=True)

        self.assertEqual(only_in_osm, [rust.PyStreet.from_string('Only In OSM utca')])

        # These is filtered out, even if it's OSM-only.
        osm_street_blacklist = relations.get_relation("gazdagret").get_config().get_osm_street_filters()
        self.assertEqual(osm_street_blacklist, ['Second Only In OSM utca'])

    def test_no_osm_street_filters(self) -> None:
        """Tests when the osm-street-filters key is missing."""
        relations = areas.make_relations(test_context.make_test_context())
        relation_name = "gh385"
        relation = relations.get_relation(relation_name)
        self.assertEqual(relation.get_config().get_osm_street_filters(), [])


class TestRelationGetAdditionalHousenumbers(unittest.TestCase):
    """Tests Relation.get_additional_housenumbers()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relations = areas.make_relations(test_context.make_test_context())
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        only_in_osm = relation.get_additional_housenumbers()
        only_in_osm_strs = [(name.get_osm_name(), [i.get_number() for i in numbers]) for name, numbers in only_in_osm]
        # Note how Second Only In OSM utca 1 is filtered out explicitly.
        self.assertEqual(only_in_osm_strs, [('Only In OSM utca', ['1'])])


def table_doc_to_string(table: List[List[yattag.Doc]]) -> List[List[str]]:
    """Unwraps an escaped matrix of yattag documents into a string matrix."""
    table_content = []
    for row in table:
        row_content = []
        for cell in row:
            row_content.append(cell.get_value())
        table_content.append(row_content)
    return table_content


class TestRelationWriteMissingHouseNumbers(unittest.TestCase):
    """Tests Relation.write_missing_housenumbers()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        ctx = test_context.make_test_context()
        file_system = test_context.TestFileSystem()
        percent_value = io.BytesIO()
        percent_value.__setattr__("close", lambda: None)
        files = {
            ctx.get_abspath("workdir/gazdagret.percent"): percent_value,
        }
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        relations = areas.make_relations(ctx)
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        expected = util.get_content(relations.get_workdir() + "/gazdagret.percent")
        ret = relation.write_missing_housenumbers()
        todo_street_count, todo_count, done_count, percent, table = ret
        self.assertEqual(todo_street_count, 3)
        self.assertEqual(todo_count, 5)
        self.assertEqual(done_count, 6)
        self.assertEqual(percent, '54.55')
        string_table = table_doc_to_string(table)
        self.assertEqual(string_table, [['Street name', 'Missing count', 'House numbers'],
                                        ['Törökugrató utca', '2', '7<br />10'],
                                        ['Tűzkő utca', '2', '1<br />2'],
                                        ['Hamzsabégi út', '1', '1']])
        percent_value.seek(0)
        actual = percent_value.read()
        self.assertEqual(actual, expected)

    def test_empty(self) -> None:
        """Tests the case when percent can't be determined."""
        ctx = test_context.make_test_context()
        percent_value = io.BytesIO()
        percent_value.__setattr__("close", lambda: None)
        files = {
            ctx.get_abspath("workdir/empty.percent"): percent_value,
        }
        file_system = test_context.TestFileSystem()
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        relations = areas.make_relations(ctx)
        relation_name = "empty"
        relation = relations.get_relation(relation_name)
        ret = relation.write_missing_housenumbers()
        _todo_street_count, _todo_count, _done_count, percent, _table = ret
        self.assertEqual(percent, '100.00')
        self.assertEqual({}, get_filters(relation))

    def test_interpolation_all(self) -> None:
        """Tests the case when the street is interpolation=all and coloring is wanted."""
        ctx = test_context.make_test_context()
        file_system = test_context.TestFileSystem()
        percent_value = io.BytesIO()
        percent_value.__setattr__("close", lambda: None)
        files = {
            ctx.get_abspath("workdir/budafok.percent"): percent_value,
        }
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        relations = areas.make_relations(ctx)
        relation_name = "budafok"
        relation = relations.get_relation(relation_name)
        ret = relation.write_missing_housenumbers()
        self.assertTrue(percent_value.tell())
        _todo_street_count, _todo_count, _done_count, _percent, table = ret
        string_table = table_doc_to_string(table)
        # Note how "12" is ordered after "2", even if a string sort would do the opposite.
        self.assertEqual(string_table, [['Street name', 'Missing count', 'House numbers'],
                                        ['Vöröskúti határsor',
                                         '4', '2, 12, 34, <span style="color: blue;">36</span>']])

    def test_sorting(self) -> None:
        """Tests that sorting is performed after range reduction."""
        ctx = test_context.make_test_context()
        file_system = test_context.TestFileSystem()
        percent_value = io.BytesIO()
        percent_value.__setattr__("close", lambda: None)
        files = {
            ctx.get_abspath("workdir/gh414.percent"): percent_value,
        }
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        relations = areas.make_relations(ctx)
        relation_name = "gh414"
        relation = relations.get_relation(relation_name)
        ret = relation.write_missing_housenumbers()
        self.assertTrue(percent_value.tell())
        _todo_street_count, _todo_count, _done_count, _percent, table = ret
        string_table = table_doc_to_string(table)
        # Note how 'A utca' is logically 5 house numbers, but it's a single range, so it's
        # ordered after 'B utca'.
        self.assertEqual(string_table, [['Street name', 'Missing count', 'House numbers'],
                                        ['B utca', '2', '1, 3'],
                                        ['A utca', '1', '2-10']])


class TestRelationWriteMissingStreets(unittest.TestCase):
    """Tests Relation.write_missing_streets()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        ctx = test_context.make_test_context()
        file_system = test_context.TestFileSystem()
        percent_value = io.BytesIO()
        percent_value.__setattr__("close", lambda: None)
        files = {
            os.path.join(ctx.get_ini().get_workdir(), "gazdagret-streets.percent"): percent_value,
        }
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        relations = areas.make_relations(ctx)
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        expected = util.get_content(relations.get_workdir() + "/gazdagret-streets.percent")
        ret = relation.write_missing_streets()
        todo_count, done_count, percent, streets = ret
        self.assertEqual(todo_count, 1)
        self.assertEqual(done_count, 4)
        self.assertEqual(percent, '80.00')
        self.assertEqual(streets, ['Only In Ref utca'])
        percent_value.seek(0)
        self.assertEqual(percent_value.read(), expected)

    def test_empty(self) -> None:
        """Tests the case when percent can't be determined."""
        ctx = test_context.make_test_context()
        file_system = test_context.TestFileSystem()
        percent_value = io.BytesIO()
        percent_value.__setattr__("close", lambda: None)
        files = {
            ctx.get_abspath("workdir/empty-streets.percent"): percent_value,
        }
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        relations = areas.make_relations(ctx)
        relation_name = "empty"
        relation = relations.get_relation(relation_name)
        ret = relation.write_missing_streets()
        self.assertTrue(percent_value.tell())
        _todo_count, _done_count, percent, _streets = ret
        self.assertEqual(percent, '100.00')


class TestRelationBuildRefHousenumbers(unittest.TestCase):
    """Tests Relation.build_ref_housenumbers()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        refdir = os.path.join(os.path.dirname(__file__), "refdir")
        relations = areas.make_relations(test_context.make_test_context())
        refpath = os.path.join(refdir, "hazszamok_20190511.tsv")
        memory_cache = util.build_reference_cache(refpath, "01")
        relation_name = "gazdagret"
        street = "Törökugrató utca"
        relation = relations.get_relation(relation_name)
        ret = relation.build_ref_housenumbers(memory_cache, street, "")
        expected = [
            'Törökugrató utca\t1\tcomment',
            'Törökugrató utca\t10\t',
            'Törökugrató utca\t11\t',
            'Törökugrató utca\t12\t',
            'Törökugrató utca\t2\t',
            'Törökugrató utca\t7\t',
        ]
        self.assertEqual(ret, expected)

    def test_missing(self) -> None:
        """Tests the case when the street is not in the reference."""
        relations = areas.make_relations(test_context.make_test_context())
        refdir = os.path.join(os.path.dirname(__file__), "refdir")
        refpath = os.path.join(refdir, "hazszamok_20190511.tsv")
        memory_cache = util.build_reference_cache(refpath, "01")
        relation_name = "gazdagret"
        street = "No such utca"
        relation = relations.get_relation(relation_name)
        ret = relation.build_ref_housenumbers(memory_cache, street, "")
        self.assertEqual(ret, [])


class TestRelationBuildRefStreets(unittest.TestCase):
    """Tests Relation.build_ref_streets()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        refdir = os.path.join(os.path.dirname(__file__), "refdir")
        refpath = os.path.join(refdir, "utcak_20190514.tsv")
        memory_cache = util.build_street_reference_cache(refpath)
        relation_name = "gazdagret"
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation(relation_name)
        ret = relation.get_config().build_ref_streets(memory_cache)
        self.assertEqual(ret, ['Törökugrató utca',
                               'Tűzkő utca',
                               'Ref Name 1',
                               'Only In Ref utca',
                               'Only In Ref Nonsense utca',
                               'Hamzsabégi út'])


class TestRelationWriteRefHousenumbers(unittest.TestCase):
    """Tests Relation.write_ref_housenumbers()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        refdir = os.path.join(os.path.dirname(__file__), "refdir")
        refpath = os.path.join(refdir, "hazszamok_20190511.tsv")
        refpath2 = os.path.join(refdir, "hazszamok_kieg_20190808.tsv")
        ctx = test_context.make_test_context()
        file_system = test_context.TestFileSystem()
        ref_value = io.BytesIO()
        ref_value.__setattr__("close", lambda: None)
        files = {
            os.path.join(ctx.get_ini().get_workdir(), "street-housenumbers-reference-gazdagret.lst"): ref_value,
        }
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        relations = areas.make_relations(ctx)
        relation_name = "gazdagret"
        expected = util.get_content(relations.get_workdir() + "/street-housenumbers-reference-gazdagret.lst")
        relation = relations.get_relation(relation_name)

        relation.write_ref_housenumbers([refpath, refpath2])

        ref_value.seek(0)
        self.assertEqual(ref_value.read(), expected)

    def test_nosuchrefcounty(self) -> None:
        """Tests the case when the refcounty code is missing in the reference."""
        refdir = os.path.join(os.path.dirname(__file__), "refdir")
        refpath = os.path.join(refdir, "hazszamok_20190511.tsv")
        ctx = test_context.make_test_context()
        file_system = test_context.TestFileSystem()
        ref_value = io.BytesIO()
        ref_value.__setattr__("close", lambda: None)
        files = {
            os.path.join(ctx.get_ini().get_workdir(), "street-housenumbers-reference-nosuchrefcounty.lst"): ref_value,
        }
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        relations = areas.make_relations(ctx)
        relation_name = "nosuchrefcounty"
        relation = relations.get_relation(relation_name)
        try:
            relation.write_ref_housenumbers([refpath])
        except KeyError:
            self.fail("write_ref_housenumbers() raised KeyError unexpectedly")

    def test_nosuchrefsettlement(self) -> None:
        """Tests the case when the refsettlement code is missing in the reference."""
        refdir = os.path.join(os.path.dirname(__file__), "refdir")
        refpath = os.path.join(refdir, "hazszamok_20190511.tsv")
        ctx = test_context.make_test_context()
        file_system = test_context.TestFileSystem()
        ref_value = io.BytesIO()
        ref_value.__setattr__("close", lambda: None)
        files = {
            os.path.join(ctx.get_ini().get_workdir(), "street-housenumbers-reference-nosuchrefsettlement.lst"): ref_value,
        }
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        relations = areas.make_relations(ctx)
        relation_name = "nosuchrefsettlement"
        relation = relations.get_relation(relation_name)
        try:
            relation.write_ref_housenumbers([refpath])
        except KeyError:
            self.fail("write_ref_housenumbers() raised KeyError unexpectedly")


class TestRelationWriteRefStreets(unittest.TestCase):
    """Tests Relation.WriteRefStreets()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        ctx = test_context.make_test_context()
        file_system = test_context.TestFileSystem()
        ref_value = io.BytesIO()
        ref_value.__setattr__("close", lambda: None)
        files = {
            os.path.join(ctx.get_ini().get_workdir(), "streets-reference-gazdagret.lst"): ref_value,
        }
        file_system.set_files(files)
        ctx.set_file_system(file_system)
        refpath = ctx.get_abspath(os.path.join("refdir", "utcak_20190514.tsv"))
        relations = areas.make_relations(ctx)
        relation_name = "gazdagret"
        relation = relations.get_relation(relation_name)
        expected = util.get_content(relations.get_workdir() + "/streets-reference-gazdagret.lst")
        relation.write_ref_streets(refpath)
        ref_value.seek(0)
        self.assertEqual(ref_value.read(), expected)


class TestRelations(unittest.TestCase):
    """Tests the Relations class."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relations = areas.make_relations(test_context.make_test_context())
        expected_relation_names = [
            "budafok",
            "empty",
            "gazdagret",
            "gellerthegy",
            "inactiverelation",
            "nosuchrefcounty",
            "nosuchrefsettlement",
            "nosuchrelation",
            "test",
            "ujbuda"
        ]
        self.assertEqual(relations.get_names(), expected_relation_names)
        self.assertTrue("inactiverelation" not in relations.get_active_names())
        osmids = sorted([relation.get_config().get_osmrelation() for relation in relations.get_relations()])
        self.assertEqual([13, 42, 42, 43, 44, 45, 66, 221998, 2702687, 2713748], osmids)
        self.assertEqual("only", relations.get_relation("ujbuda").get_config().should_check_missing_streets())

        relations.activate_all(True)
        self.assertTrue("inactiverelation" in relations.get_active_names())

        # Allow seeing data of a relation even if it's not in relations.yaml.
        relations.get_relation("gh195")

        # Test limit_to_refcounty().
        # 01
        self.assertTrue("gazdagret" in relations.get_active_names())
        # 43
        self.assertTrue("budafok" in relations.get_active_names())
        relations.limit_to_refcounty("01")
        self.assertTrue("gazdagret" in relations.get_active_names())
        self.assertTrue("budafok" not in relations.get_active_names())

        # Test limit_to_refsettlement().
        # 011
        self.assertTrue("gazdagret" in relations.get_active_names())
        # 99
        self.assertTrue("nosuchrefsettlement" in relations.get_active_names())
        relations.limit_to_refsettlement("99")
        self.assertTrue("gazdagret" not in relations.get_active_names())
        self.assertTrue("nosuchrefsettlement" in relations.get_active_names())


class TestRelationConfigMissingStreets(unittest.TestCase):
    """Tests RelationConfig.should_check_missing_streets()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relation_name = "ujbuda"
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation(relation_name)
        ret = relation.get_config().should_check_missing_streets()
        self.assertEqual(ret, "only")

    def test_empty(self) -> None:
        """Tests the default value."""
        relation_name = "empty"
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation(relation_name)
        self.assertEqual(relation.get_name(), "empty")
        ret = relation.get_config().should_check_missing_streets()
        self.assertEqual(ret, "yes")

    def test_nosuchrelation(self) -> None:
        """Tests a relation without a filter file."""
        relation_name = "nosuchrelation"
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation(relation_name)
        ret = relation.get_config().should_check_missing_streets()
        self.assertEqual(ret, "yes")


class TestRelationConfigLetterSuffixStyle(unittest.TestCase):
    """Tests RelationConfig.get_letter_suffix_style()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relation_name = "empty"
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation(relation_name)
        self.assertEqual(relation.get_config().get_letter_suffix_style(), rust.PyLetterSuffixStyle.upper())
        config = relation.get_config()
        config.set_letter_suffix_style(rust.PyLetterSuffixStyle.lower())
        relation.set_config(config)
        self.assertEqual(relation.get_config().get_letter_suffix_style(), rust.PyLetterSuffixStyle.lower())


class TestRefmegyeGetName(unittest.TestCase):
    """Tests refcounty_get_name()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        ctx = test_context.make_test_context()
        relations = areas.make_relations(ctx)
        self.assertEqual(relations.refcounty_get_name("01"), "Budapest")
        self.assertEqual(relations.refcounty_get_name("99"), "")


class TestRefmegyeGetReftelepulesIds(unittest.TestCase):
    """Tests refcounty_get_refsettlement_ids()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        ctx = test_context.make_test_context()
        relations = areas.make_relations(ctx)
        self.assertEqual(relations.refcounty_get_refsettlement_ids("01"), ["011", "012"])
        self.assertEqual(relations.refcounty_get_refsettlement_ids("99"), [])


class TestReftelepulesGetName(unittest.TestCase):
    """Tests refsettlement_get_name()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        ctx = test_context.make_test_context()
        relations = areas.make_relations(ctx)
        self.assertEqual(relations.refsettlement_get_name("01", "011"), "Újbuda")
        self.assertEqual(relations.refsettlement_get_name("99", ""), "")
        self.assertEqual(relations.refsettlement_get_name("01", "99"), "")


class TestRelationsGetAliases(unittest.TestCase):
    """Tests Relalations.get_aliases()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        ctx = test_context.make_test_context()
        relations = areas.make_relations(ctx)
        # Expect an alias -> canonicalname map.
        expected = {
            "budapest_22": "budafok"
        }
        self.assertEqual(relations.get_aliases(), expected)


class TestRelationStreetIsEvenOdd(unittest.TestCase):
    """Tests RelationConfig.get_street_is_even_odd()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        ctx = test_context.make_test_context()
        relations = areas.make_relations(ctx)
        relation = relations.get_relation("gazdagret")
        self.assertFalse(relation.get_config().get_street_is_even_odd("Hamzsabégi út"))

        self.assertTrue(relation.get_config().get_street_is_even_odd("Teszt utca"))


class TestRelationShowRefstreet(unittest.TestCase):
    """Tests RelationConfig.should_show_ref_street()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation("gazdagret")
        self.assertFalse(relation.should_show_ref_street("Törökugrató utca"))
        self.assertTrue(relation.should_show_ref_street("Hamzsabégi út"))


class TestRelationIsActive(unittest.TestCase):
    """Tests RelationConfig.is_active()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation("gazdagret")
        self.assertTrue(relation.get_config().is_active())


class TestMakeTurboQueryForStreets(unittest.TestCase):
    """Tests make_turbo_query_for_streets()."""
    def test_happy(self) -> None:
        """Tests the happy path."""
        relations = areas.make_relations(test_context.make_test_context())
        relation = relations.get_relation("gazdagret")
        fro = ["A2"]
        ret = areas.make_turbo_query_for_streets(relation, fro)
        expected = """[out:json][timeout:425];
rel(2713748)->.searchRelation;
area(3602713748)->.searchArea;
(rel(2713748);
way["name"="A2"](r.searchRelation);
way["name"="A2"](area.searchArea);
);
out body;
>;
out skel qt;
{{style:
relation{width:3}
way{color:blue; width:4;}
}}"""
        self.assertEqual(ret, expected)


if __name__ == '__main__':
    unittest.main()
