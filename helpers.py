#!/usr/bin/env python3
#
# Copyright (c) 2019 Miklos Vajna and contributors.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The helpers module contains functionality shared between other modules."""

import configparser
import re
import os
import pickle
from typing import Any
from typing import Callable
from typing import Dict
from typing import Iterable
from typing import List
from typing import Sequence
from typing import TextIO
from typing import Tuple
from typing import cast
import yaml


class Range:
    """A range object represents an odd or even range of integer numbers."""
    def __init__(self, start: int, end: int) -> None:
        self.__start = start
        self.__end = end
        self.__is_odd = start % 2 == 1

    def get_start(self) -> int:
        """The smallest integer."""
        return self.__start

    def get_end(self) -> int:
        """The largest integer."""
        return self.__end

    def __contains__(self, item: int) -> bool:
        if self.__is_odd != (item % 2 == 1):
            return False
        if self.__start <= item <= self.__end:
            return True
        return False

    def __repr__(self) -> str:
        return "Range(start=%s, end=%s, is_odd=%s)" % (self.__start, self.__end, self.__is_odd)

    def __eq__(self, other: object) -> bool:
        other_range = cast(Range, other)
        if self.__start != other_range.get_start():
            return False
        if self.__end != other_range.get_end():
            return False
        return True


class Ranges:
    """A Ranges object contains an item if any of its Range objects contains it."""
    def __init__(self, items: List[Range]) -> None:
        self.__items = items

    def get_items(self) -> List[Range]:
        """The list of contained Range objects."""
        return self.__items

    def __contains__(self, item: int) -> bool:
        for i in self.__items:
            if item in i:
                return True
        return False

    def __repr__(self) -> str:
        return "Ranges(items=%s)" % self.__items

    def __eq__(self, other: object) -> bool:
        other_ranges = cast(Ranges, other)
        return self.__items == other_ranges.get_items()


def get_relation_missing_streets(datadir: str, relation_name: str) -> str:
    """Return value can be yes, no and only. Current default is "no", and "yes" is not yet handled."""
    relation_path = os.path.join(datadir, "relation-%s.yaml" % relation_name)
    if os.path.exists(relation_path):
        with open(relation_path) as sock:
            # See if config wants to map:
            root = yaml.load(sock)
            if "suspicious-relations" in root:
                return cast(str, root["suspicious-relations"])

    return "no"


def get_reftelepules_list_from_yaml(
        reftelepules_list: List[str],
        value: Dict[str, Any]
) -> List[str]:
    """Determines street-level and range-level reftelepules overrides."""
    if "reftelepules" in value.keys():
        reftelepules = cast(str, value["reftelepules"])
        reftelepules_list = [reftelepules]
    if "ranges" in value.keys():
        for street_range in value["ranges"]:
            street_range_dict = cast(Dict[str, str], street_range)
            if "reftelepules" in street_range_dict.keys():
                reftelepules_list.append(street_range_dict["reftelepules"])

    return reftelepules_list


def parse_relation_yaml(
        root: Dict[str, Any],
        street: str,
        refstreets: Dict[str, str],
        reftelepules_list: List[str]
) -> Tuple[Dict[str, str], List[str]]:
    """Parses the yaml of a single relation."""
    if "refstreets" in root.keys():
        # From OSM name to ref name.
        refstreets = cast(Dict[str, str], root["refstreets"])
    if "filters" in root.keys():
        # street-specific reftelepules override.
        filters = cast(Dict[str, Any], root["filters"])
        for filter_street, value in filters.items():
            if filter_street == street:
                reftelepules_list = get_reftelepules_list_from_yaml(reftelepules_list, value)

    return refstreets, reftelepules_list


def get_street_details(datadir: str, street: str, relation_name: str) -> Tuple[str, List[str], str, str]:
    """Determines the ref codes, street name and type for a street in a relation."""
    with open(os.path.join(datadir, "relations.yaml")) as sock:
        relations = yaml.load(sock)
    relation = relations[relation_name]
    refmegye = relation["refmegye"]
    reftelepules_list = [relation["reftelepules"]]

    refstreets = {}  # type: Dict[str, str]
    if os.path.exists(os.path.join(datadir, "relation-%s.yaml" % relation_name)):
        with open(os.path.join(datadir, "relation-%s.yaml" % relation_name)) as sock:
            # See if config wants to map:
            root = yaml.load(sock)
            refstreets, reftelepules_list = parse_relation_yaml(root, street, refstreets, reftelepules_list)

    if street in refstreets.keys():
        street = refstreets[street]

    tokens = street.split(' ')
    street_name = " ".join(tokens[:-1])
    street_type = tokens[-1]
    return refmegye, sorted(set(reftelepules_list)), street_name, street_type


def sort_numerically(strings: Iterable[str]) -> List[str]:
    """Sorts strings according to their numerical value, not alphabetically."""
    return sorted(strings, key=split_house_number)


def split_house_number(house_number: str) -> Tuple[int, str]:
    """Splits house_number into a numerical and a remainder part."""
    match = re.search(r"^([0-9]*)([^0-9].*|)$", house_number)
    if not match:  # pragma: no cover
        return (0, '')
    number = 0
    try:
        number = int(match.group(1))
    except ValueError:
        pass
    return (number, match.group(2))


def sort_streets_csv(data: str) -> str:
    """
    Sorts TSV Overpass street name result with visual partitioning.

    See split_street_line for sorting rules.
    """
    return process_csv_body(sort_streets, data)


def sort_streets(lines: Iterable[str]) -> List[str]:
    """
    Sorts the body of a TSV Overpass street name result with visual partitioning.

    See split_street_line for sorting rules.
    """
    return sorted(lines, key=split_street_line)


def split_street_line(line: str) -> Tuple[bool, str, str, str, Tuple[int, str]]:
    """
    Augment TSV Overpass street name result lines to aid sorting.

    It prepends a bool to indicate whether the street is missing a name, thus
    streets with missing names are ordered last.
    oid is interpreted numerically while other fields are taken alphabetically.
    """
    field = line.split('\t')
    oid = get_array_nth(field, 0)
    name = get_array_nth(field, 1)
    highway = get_array_nth(field, 2)
    service = get_array_nth(field, 3)
    missing_name = name == ''
    return (missing_name, name, highway, service, split_house_number(oid))


def process_csv_body(fun: Callable[[Iterable[str]], List[str]], data: str) -> str:
    """
    Process the body of a CSV/TSV with the given function while keeping the header intact.
    """
    lines = data.split('\n')
    header = lines[0] if lines else ''
    body = lines[1:] if lines else ''
    result = [header] + fun(body)
    return '\n'.join(result)


def sort_housenumbers_csv(data: str) -> str:
    """
    Sorts TSV Overpass house numbers result with visual partitioning.

    See split_housenumber_line for sorting rules.
    """
    return process_csv_body(sort_housenumbers, data)


def sort_housenumbers(lines: Iterable[str]) -> List[str]:
    """
    Sorts the body of a TSV Overpass house numbers result with visual partitioning.

    See split_housenumber_line for sorting rules.
    """
    return sorted(lines, key=split_housenumber_line)


def split_housenumber_line(line: str) -> Tuple[str, bool, bool, str, Tuple[int, str], str,
                                               Tuple[int, str], Iterable[str], Tuple[int, str]]:
    """
    Augment TSV Overpass house numbers result lines to aid sorting.

    It prepends two bools to indicate whether an entry is missing either a house number, a house name
    or a conscription number.
    Entries lacking either a house number or all of the above IDs come first.
    The following fields are interpreted numerically: oid, house number, conscription number.
    """
    field = line.split('\t')

    oid = get_array_nth(field, 0)
    street = get_array_nth(field, 1)
    housenumber = get_array_nth(field, 2)
    postcode = get_array_nth(field, 3)
    housename = get_array_nth(field, 4)
    cons = get_array_nth(field, 5)
    tail = field[6:] if len(field) > 6 else []

    have_housenumber = housenumber != ''
    have_houseid = have_housenumber or housename != '' or cons != ''
    return (postcode, have_houseid, have_housenumber, street,
            split_house_number(housenumber),
            housename, split_house_number(cons), tail, split_house_number(oid))


def get_array_nth(arr: Sequence[str], index: int) -> str:
    """Gets the nth element of arr, returns en empty string on error."""
    return arr[index] if len(arr) > index else ''


def get_only_in_first(first: List[Any], second: List[Any]) -> List[Any]:
    """Returns items which are in first, but not in second."""
    ret = []
    for i in first:
        if i not in second:
            ret.append(i)
    return ret


def get_in_both(first: List[Any], second: List[Any]) -> List[Any]:
    """Returns items which are in both first and second."""
    ret = []
    for i in first:
        if i in second:
            ret.append(i)
    return ret


def git_link(version: str, prefix: str) -> str:
    """Generates a HTML link based on a website prefix and a git-describe version."""
    commit_hash = re.sub(".*-g", "", version)
    return "<a href=\"" + prefix + commit_hash + "\">" + version + "</a>"


def get_nth_column(path: str, column: int) -> List[str]:
    """Reads the content of path, interprets its content as tab-separated values, finally returns
    the values of the nth column. If a row has less columns, that's silentely ignored."""
    ret = []

    with open(path) as sock:
        first = True
        for line in sock.readlines():
            if first:
                first = False
                continue

            tokens = line.strip().split('\t')
            if len(tokens) < column + 1:
                continue

            ret.append(tokens[column])

    return ret


def get_streets(workdir: str, relation_name: str) -> List[str]:
    """Reads list of streets for an area from OSM."""
    ret = get_nth_column(os.path.join(workdir, "streets-%s.csv" % relation_name), 1)
    house_numbers = os.path.join(workdir, "street-housenumbers-%s.csv" % relation_name)
    if os.path.exists(house_numbers):
        ret += get_nth_column(house_numbers, 1)
    return sorted(set(ret))


def get_workdir(config: configparser.ConfigParser) -> str:
    """Gets the directory which is writable."""
    return config.get('wsgi', 'workdir').strip()


def process_template(buf: str, osmrelation: int) -> str:
    """Turns an overpass query template to an actual query."""
    buf = buf.replace("@RELATION@", str(osmrelation))
    # area is relation + 3600000000 (3600000000 == relation), see js/ide.js
    # in https://github.com/tyrasd/overpass-turbo
    buf = buf.replace("@AREA@", str(3600000000 + osmrelation))
    return buf


def get_content(workdir: str, path: str) -> str:
    """Gets the content of a file in workdir."""
    ret = ""
    with open(os.path.join(workdir, path)) as sock:
        ret = sock.read()
    return ret


def load_normalizers(datadir: str, relation_name: str) -> Tuple[Dict[str, Ranges], Dict[str, str], List[str]]:
    """Loads filters which allow silencing false positives. The return value is a tuple of the
    normalizers itself and an OSM name -> ref name dictionary."""
    filter_dict = {}  # type: Dict[str, Ranges]
    ref_streets = {}  # type: Dict[str, str]
    street_filters = []  # type: List[str]

    path = os.path.join(datadir, "relation-%s.yaml" % relation_name)
    if not os.path.exists(path):
        return filter_dict, ref_streets, street_filters

    with open(path) as sock:
        root = yaml.load(sock)

    if "filters" in root.keys():
        filters = root["filters"]
        for street in filters.keys():
            i = []
            if "ranges" not in filters[street]:
                continue
            for start_end in filters[street]["ranges"]:
                i.append(Range(int(start_end["start"]), int(start_end["end"])))
            filter_dict[street] = Ranges(i)

    if "refstreets" in root.keys():
        ref_streets = root["refstreets"]

    if "street-filters" in root.keys():
        street_filters = root["street-filters"]

    return filter_dict, ref_streets, street_filters


def tsv_to_list(sock: TextIO) -> List[List[str]]:
    """Turns a tab-separated table into a list of lists."""
    table = []

    for line in sock.readlines():
        if not line.strip():
            continue
        cells = line.split("\t")
        table.append(cells)

    return table


def html_table_from_list(table: List[List[str]]) -> str:
    """Produces a HTML table from a list of lists."""
    ret = []
    ret.append('<table rules="all" frame="border" cellpadding="4" class="sortable">')
    for row_index, row_content in enumerate(table):
        ret.append("<tr>")
        for cell in row_content:
            if row_index == 0:
                ret.append('<th align="left" valign="center"><a href="#">' + cell + "</a></th>")
            else:
                ret.append('<td align="left" valign="top">' + cell + "</td>")
        ret.append("</tr>")
    ret.append("</table>")
    return "".join(ret)


def normalize(house_numbers: str, street_name: str,
              normalizers: Dict[str, Ranges]) -> List[str]:
    """Strips down string input to bare minimum that can be interpreted as an
    actual number. Think about a/b, a-b, and so on."""
    ret = []
    for house_number in house_numbers.split('-'):
        try:
            number = int(re.sub(r"([0-9]+).*", r"\1", house_number))
        except ValueError:
            continue

        if street_name in normalizers.keys():
            # Have a custom filter.
            normalizer = normalizers[street_name]
        else:
            # Default sanity checks.
            default = [Range(1, 999), Range(2, 998)]
            normalizer = Ranges(default)
        if number not in normalizer:
            continue

        ret.append(str(number))
    return ret


def get_house_numbers_from_lst(
        workdir: str,
        relation_name: str,
        street_name: str,
        ref_street: str,
        normalizers: Dict[str, Ranges]
) -> List[str]:
    """Gets house numbers from reference."""
    house_numbers = []  # type: List[str]
    lst_street_name = ref_street
    prefix = lst_street_name + " "
    with open(os.path.join(workdir, "street-housenumbers-reference-%s.lst" % relation_name)) as sock:
        for line in sock.readlines():
            line = line.strip()
            if line.startswith(prefix):
                house_number = line.replace(prefix, '')
                house_numbers += normalize(house_number, street_name, normalizers)
    return sort_numerically(set(house_numbers))


def get_streets_from_lst(workdir: str, relation_name: str) -> List[str]:
    """Gets streets from reference."""
    streets = []  # type: List[str]
    with open(os.path.join(workdir, "streets-reference-%s.lst" % relation_name)) as sock:
        for line in sock.readlines():
            line = line.strip()
            streets.append(line)
    return sorted(set(streets))


def get_house_numbers_from_csv(
        workdir: str,
        relation_name: str,
        street_name: str,
        normalizers: Dict[str, Ranges]
) -> List[str]:
    """Gets house numbers from the overpass query."""
    house_numbers = []  # type: List[str]
    with open(os.path.join(workdir, "street-housenumbers-%s.csv" % relation_name)) as sock:
        first = True
        for line in sock.readlines():
            if first:
                first = False
                continue
            tokens = line.strip().split('\t')
            if len(tokens) < 3:
                continue
            if tokens[1] != street_name:
                continue
            house_numbers += normalize(tokens[2], street_name, normalizers)
    return sort_numerically(set(house_numbers))


def get_suspicious_streets(
        datadir: str,
        workdir: str,
        relation_name: str
) -> Tuple[List[Tuple[str, List[str]]], List[Tuple[str, List[str]]]]:
    """Tries to find streets which do have at least one house number, but are suspicious as other
    house numbers are probably missing."""
    suspicious_streets = []
    done_streets = []

    street_names = get_streets(workdir, relation_name)
    normalizers, ref_streets, _street_filters = load_normalizers(datadir, relation_name)
    for street_name in street_names:
        ref_street = street_name
        # See if we need to map the OSM name to ref name.
        if street_name in ref_streets.keys():
            ref_street = ref_streets[street_name]

        reference_house_numbers = get_house_numbers_from_lst(workdir, relation_name, street_name,
                                                             ref_street, normalizers)
        osm_house_numbers = get_house_numbers_from_csv(workdir, relation_name, street_name, normalizers)
        only_in_reference = get_only_in_first(reference_house_numbers, osm_house_numbers)
        in_both = get_in_both(reference_house_numbers, osm_house_numbers)
        if only_in_reference:
            suspicious_streets.append((street_name, only_in_reference))
        if in_both:
            done_streets.append((street_name, in_both))
    # Sort by length.
    suspicious_streets.sort(key=lambda result: len(result[1]), reverse=True)

    return suspicious_streets, done_streets


def get_suspicious_relations(datadir: str, workdir: str, relation_name: str) -> Tuple[List[str], List[str]]:
    """Tries to find missing streets in a relation."""
    reference_streets = get_streets_from_lst(workdir, relation_name)
    _, ref_streets, street_blacklist = load_normalizers(datadir, relation_name)
    osm_streets = []
    for street in get_streets(workdir, relation_name):
        if street in ref_streets.keys():
            street = ref_streets[street]
        osm_streets.append(street)

    only_in_reference = get_only_in_first(reference_streets, osm_streets)
    only_in_reference = [i for i in only_in_reference if i not in street_blacklist]
    in_both = get_in_both(reference_streets, osm_streets)

    return only_in_reference, in_both


def build_reference_cache(local: str) -> Dict[str, Dict[str, Dict[str, List[str]]]]:
    """Builds an in-memory cache from the reference on-disk TSV (house number version)."""
    memory_cache = {}  # type: Dict[str, Dict[str, Dict[str, List[str]]]]

    disk_cache = local + ".pickle"
    if os.path.exists(disk_cache):
        with open(disk_cache, "rb") as sock_cache:
            memory_cache = pickle.load(sock_cache)
            return memory_cache

    with open(local, "r") as sock:
        first = True
        while True:
            line = sock.readline()
            if first:
                first = False
                continue

            if not line:
                break

            refmegye, reftelepules, street, num = line.strip().split("\t")
            if refmegye not in memory_cache.keys():
                memory_cache[refmegye] = {}
            if reftelepules not in memory_cache[refmegye].keys():
                memory_cache[refmegye][reftelepules] = {}
            if street not in memory_cache[refmegye][reftelepules].keys():
                memory_cache[refmegye][reftelepules][street] = []
            memory_cache[refmegye][reftelepules][street].append(num)
    with open(disk_cache, "wb") as sock_cache:
        pickle.dump(memory_cache, sock_cache)
    return memory_cache


def build_street_reference_cache(local_streets: str) -> Dict[str, Dict[str, List[str]]]:
    """Builds an in-memory cache from the reference on-disk TSV (street version)."""
    memory_cache = {}  # type: Dict[str, Dict[str, List[str]]]

    disk_cache = local_streets + ".pickle"
    if os.path.exists(disk_cache):
        with open(disk_cache, "rb") as sock_cache:
            memory_cache = pickle.load(sock_cache)
            return memory_cache

    with open(local_streets, "r") as sock:
        first = True
        while True:
            line = sock.readline()
            if first:
                first = False
                continue

            if not line:
                break

            refmegye, reftelepules, street = line.strip().split("\t")
            if refmegye not in memory_cache.keys():
                memory_cache[refmegye] = {}
            if reftelepules not in memory_cache[refmegye].keys():
                memory_cache[refmegye][reftelepules] = []
            memory_cache[refmegye][reftelepules].append(street)
    with open(disk_cache, "wb") as sock_cache:
        pickle.dump(memory_cache, sock_cache)
    return memory_cache


def house_numbers_of_street(
        datadir: str,
        reference: Dict[str, Dict[str, Dict[str, List[str]]]],
        relation_name: str,
        street: str
) -> List[str]:
    """Gets house numbers for a street locally."""
    refmegye, reftelepules_list, street_name, street_type = get_street_details(datadir, street, relation_name)
    street = street_name + " " + street_type
    ret = []  # type: List[str]
    for reftelepules in reftelepules_list:
        if street in reference[refmegye][reftelepules].keys():
            house_numbers = reference[refmegye][reftelepules][street]
            ret += [street + " " + i for i in house_numbers]

    return ret


def streets_of_relation(datadir: str, reference: Dict[str, Dict[str, List[str]]], relation_name: str) -> List[str]:
    """Gets street names for a relation from a reference."""
    with open(os.path.join(datadir, "relations.yaml")) as sock:
        relations = yaml.load(sock)
    relation = relations[relation_name]
    refmegye = relation["refmegye"]
    reftelepules = relation["reftelepules"]

    return reference[refmegye][reftelepules]


def get_reference_housenumbers(reference: str, datadir: str, workdir: str, relation_name: str) -> None:
    """Gets known house numbers (not their coordinates) from a reference site, based on street names
    from OSM."""
    memory_cache = build_reference_cache(reference)

    streets = get_streets(workdir, relation_name)

    lst = []  # type: List[str]
    for street in streets:
        lst += house_numbers_of_street(datadir, memory_cache, relation_name, street)

    lst = sorted(set(lst))
    sock = open(os.path.join(workdir, "street-housenumbers-reference-%s.lst" % relation_name), "w")
    for line in lst:
        sock.write(line + "\n")
    sock.close()


def get_reference_streets(reference: str, datadir: str, workdir: str, relation_name: str) -> None:
    """Gets known streets (not their coordinates) from a reference site, based on relation names
    from OSM."""
    memory_cache = build_street_reference_cache(reference)

    lst = streets_of_relation(datadir, memory_cache, relation_name)

    lst = sorted(set(lst))
    sock = open(os.path.join(workdir, "streets-reference-%s.lst" % relation_name), "w")
    for line in lst:
        sock.write(line + "\n")
    sock.close()


def get_relations(datadir: str) -> Dict[str, Any]:
    """Returns a name -> properties dictionary."""
    with open(os.path.join(datadir, "relations.yaml")) as sock:
        root = {}  # type: Dict[str, Any]
        root = yaml.load(sock)
        return root


def get_streets_query(datadir: str, relations: Dict[str, Any], relation: str) -> str:
    """Produces a query which lists streets in relation."""
    with open(os.path.join(datadir, "streets-template.txt")) as sock:
        return process_template(sock.read(), relations[relation]["osmrelation"])


def write_streets_result(workdir: str, relation: str, result_from_overpass: str) -> None:
    """Writes the result for overpass of get_streets_query()."""
    result = sort_streets_csv(result_from_overpass)
    with open(os.path.join(workdir, "streets-%s.csv" % relation), mode="w") as sock:
        sock.write(result)


def get_street_housenumbers_query(datadir: str, relations: Dict[str, Any], relation: str) -> str:
    """Produces a query which lists house numbers in relation."""
    with open(os.path.join(datadir, "street-housenumbers-template.txt")) as sock:
        return process_template(sock.read(), relations[relation]["osmrelation"])


def write_street_housenumbers(workdir: str, relation: str, result_from_overpass: str) -> None:
    """Writes the result for overpass of get_street_housenumbers_query()."""
    result = sort_housenumbers_csv(result_from_overpass)
    with open(os.path.join(workdir, "street-housenumbers-%s.csv" % relation), mode="w") as sock:
        sock.write(result)


def write_suspicious_streets_result(
        datadir: str,
        workdir: str,
        relation: str
) -> Tuple[int, int, int, str, List[List[str]]]:
    """Calculate a write stat for the house number coverage of a relation."""
    suspicious_streets, done_streets = get_suspicious_streets(datadir, workdir, relation)
    todo_count = 0
    table = []
    table.append(["Utcanév", "Hiányzik db", "Házszámok"])
    for result in suspicious_streets:
        # House number, # of only_in_reference items.
        row = []
        row.append(result[0])
        row.append(str(len(result[1])))
        # only_in_reference items.
        row.append(", ".join(result[1]))
        todo_count += len(result[1])
        table.append(row)
    done_count = 0
    for result in done_streets:
        done_count += len(result[1])
    if done_count > 0 or todo_count > 0:
        percent = "%.2f" % (done_count / (done_count + todo_count) * 100)
    else:
        percent = "N/A"

    # Write the bottom line to a file, so the index page show it fast.
    with open(os.path.join(workdir, relation + ".percent"), "w") as sock:
        sock.write(percent)

    todo_street_count = len(suspicious_streets)
    return todo_street_count, todo_count, done_count, percent, table


def write_missing_relations_result(datadir: str, workdir: str, relation: str) -> Tuple[int, int, str, List[List[str]]]:
    """Calculate a write stat for the street coverage of a relation."""
    todo_streets, done_streets = get_suspicious_relations(datadir, workdir, relation)
    table = []
    table.append(["Utcanév"])
    for street in todo_streets:
        table.append([street])
    todo_count = len(todo_streets)
    done_count = len(done_streets)
    if done_count > 0 or todo_count > 0:
        percent = "%.2f" % (done_count / (done_count + todo_count) * 100)
    else:
        percent = "N/A"

    # Write the bottom line to a file, so the index page show it fast.
    with open(os.path.join(workdir, relation + "-streets.percent"), "w") as sock:
        sock.write(percent)

    return todo_count, done_count, percent, table

# vim:set shiftwidth=4 softtabstop=4 expandtab:
