#!/usr/bin/python3

# Python script (>= 3.6) to fix wrongly formatted tagtog ann.jsons when html entities appeared in the text
# (bug found in tagtog prior fix in version 3.2019-W39.x)
#
# The error only happened if the text contained textual html entities that had to be shown unescaped (e.g. "&amp;"),
# but actually and wrongly were shown as escaped (e.g. "&"). This resulted in both wrong offsets and wrong textual
# annotations.
#
# The fix consists of transforming the inputted perhaps-wrongly ann.json file (together with its plain.html file) and
# outputting a corrected ann.json file, if indeed any correcting transformation was done.
#
#
# You can use this file as a script or as a python module (`from fix_html_entities import fix_anndoc`).
#
# As a script, the default is to print the transformed annjson (if at all) to standard output. Any other warning
# is printed to stderr. You can redirect the output to an alternative fixed ann.json file, or to the original ann.json file.
#
# As a module, use `fix_anndoc` in your own python code to your best convenience.
#
# Finally, optionally you can POST the fixed ann.json files back to tagtog.
#
#
# CAUTION: please make sure to BACK UP your ann.json files before you run this script.
#


import sys
from bs4 import BeautifulSoup
import re
import json
# import pprint
# pp = pprint.PrettyPrinter()


assert sys.version_info.major == 3 and sys.version_info.minor >= 6, "This script requires >= Python 3.6"


def fix_anndoc(plainhtml_filename, annjson_filename):
    """
    :param plainhtml_filename: the path to a plain.html file (only content)
    :param annjson_filename: the path to the associated ann.json file with annotations
    :return: None if no transformation was done to the original ann.json, otherwise a json string with the new transformed annjson
    """

    with open(plainhtml_filename) as plainhtml_file:
        plain_html = BeautifulSoup(plainhtml_file, "html.parser")

    with open(annjson_filename) as annjson_file:
        annjson = json.load(annjson_file)

    were_changes_made = False
    fixed_entities = []
    for part in plain_html.find_all(id=re.compile('^s')):
        part_html_string = str(part)

        part_entities = [e for e in annjson["entities"] if e["part"] == part["id"]]

        # Only change something if we do find a doubled escaped entity in the part
        if not re.search(r"&amp;[#xa-zA-Z0-9]+;", part_html_string):
            fixed_entities += part_entities
        else:
            were_changes_made = True

            # Only change something if the part had annotated entities
            if part_entities:
                part_entities = sorted(part_entities, key=lambda e: e["offsets"][0]["start"])
                part_string = part.string

                # Get HTML entities in text
                html_entities = re.finditer(r"&[#xa-zA-Z0-9]+;", part_string)
                adjusted_offset_so_far = 0
                adjusted_offset_next = 0
                subs = []
                for match in html_entities:
                    adjusted_offset = (len(match.group(0)) - 1)  # -1 due to the symbol counted before as a single char
                    adjusted_offset_next += adjusted_offset

                    sub = {
                        "actual_text": match.group(0),
                        "actual_start": match.start(),
                        "actual_end": match.end(),
                        "adjusted_offset": adjusted_offset,
                        "adjusted_offset_so_far": adjusted_offset_so_far,
                        "adjusted_offset_next": adjusted_offset_next,
                        "wrong_text": BeautifulSoup(match.group(0), "html.parser").string,
                        "wrong_start": match.start() - adjusted_offset_so_far,
                        "wrong_end": match.start() - adjusted_offset_so_far + 1  # +1 due to the symbol written as a single char
                    }

                    adjusted_offset_so_far = adjusted_offset_next

                    subs.append(sub)

                # pp.pprint(subs)

                # Rewrite entities' start offset and start
                subs_index = 0
                adjusted_offset_so_far = 0
                for e in part_entities:
                    wrong_e_start = e["offsets"][0]["start"]
                    adjusted_start = wrong_e_start

                    # Rewrite entity start offset --> actual_e_start
                    while subs_index < len(subs):
                        sub = subs[subs_index]

                        if sub["wrong_end"] <= wrong_e_start:
                            adjusted_offset_so_far += sub["adjusted_offset"]
                            subs_index += 1
                        else:
                            adjusted_start += adjusted_offset_so_far
                            break

                    actual_e_start = adjusted_start

                    # Rewrite entity text --> actual_e_text, ...
                    # ... char by char considering that some are correct, and some others must be transformed
                    wrong_e_text = e["offsets"][0]["text"]
                    actual_e_text = ""
                    wrong_char_end = wrong_e_start
                    for char in iter(wrong_e_text):
                        try:
                            sub = subs[subs_index]
                        except IndexError:
                            sub = None

                        wrong_char_end += 1

                        if sub and sub["wrong_end"] == wrong_char_end:
                            assert char == sub["wrong_text"]
                            actual_e_text += sub["actual_text"]

                            adjusted_offset_so_far += sub["adjusted_offset"]
                            subs_index += 1
                        else:
                            actual_e_text += char

                    print(f"""WARNING; transforming entity (part={part["id"]}): [{wrong_e_start} {wrong_e_text}] \u2192 [{actual_e_start} {actual_e_text}]""", file=sys.stderr)

                    # Change entity
                    e["offsets"][0]["start"] = actual_e_start
                    e["offsets"][0]["text"] = actual_e_text

                    fixed_entities += [e]

    if were_changes_made:
        annjson["entities"] = fixed_entities
        annjson = json.dumps(annjson, separators=(',', ':'), ensure_ascii=False)
        return annjson
    else:
        print("Nothing done. Everything seems to be OK with the annjson file:", annjson_filename, file=sys.stderr)
        return None


def main():
    if len(sys.argv) < 3:
        print("You have to pass the 2 parameters: plain.html file and ann.json file. Otherwise there is nothing to do. Given parameters:", sys.argv, file=sys.stderr)
        sys.exit(-1)

    plainhtml_filename = sys.argv[1]
    annjson_filename = sys.argv[2]

    transformed_annjson = fix_anndoc(plainhtml_filename, annjson_filename)

    if transformed_annjson:
        print(transformed_annjson)


if __name__ == "__main__":
    main()
