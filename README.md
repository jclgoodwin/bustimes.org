# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| accounts/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| accounts/admin.py                                               |       41 |        0 |    100% |           |
| accounts/forms.py                                               |       50 |        0 |    100% |           |
| accounts/models.py                                              |       25 |        0 |    100% |           |
| accounts/tests.py                                               |       99 |        0 |    100% |           |
| accounts/urls.py                                                |        4 |        0 |    100% |           |
| accounts/views.py                                               |       61 |        1 |     98% |       108 |
| api/\_\_init\_\_.py                                             |        0 |        0 |    100% |           |
| api/api.py                                                      |       11 |        0 |    100% |           |
| api/filters.py                                                  |       61 |        5 |     92% |     53-57 |
| api/serializers.py                                              |      114 |        0 |    100% |           |
| api/tests.py                                                    |        7 |        0 |    100% |           |
| api/views.py                                                    |       92 |        5 |     95% |133, 140-147 |
| buses/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| buses/context\_processors.py                                    |        7 |        0 |    100% |           |
| buses/jinja2.py                                                 |       36 |        2 |     94% |    40, 61 |
| buses/settings.py                                               |      112 |       21 |     81% |97-105, 125, 208, 227-235, 252-268, 320 |
| buses/tests.py                                                  |        5 |        0 |    100% |           |
| buses/urls.py                                                   |        6 |        0 |    100% |           |
| buses/utils.py                                                  |       24 |        1 |     96% |        27 |
| busstops/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| busstops/admin.py                                               |      323 |       16 |     95% |103-109, 184, 243-251, 333-334, 380, 455, 459, 508, 540, 584, 588, 612, 616 |
| busstops/forms.py                                               |       46 |        0 |    100% |           |
| busstops/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| busstops/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| busstops/management/commands/import\_noc.py                     |      130 |        3 |     98% |155, 184, 246 |
| busstops/management/commands/naptan\_new.py                     |      150 |        5 |     97% |47, 100, 151, 211, 256 |
| busstops/management/commands/nptg\_new.py                       |       94 |        7 |     93% |148, 158, 163, 169-170, 172-173 |
| busstops/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| busstops/management/tests/test\_import\_ie.py                   |       63 |        0 |    100% |           |
| busstops/management/tests/test\_import\_naptan.py               |       67 |        0 |    100% |           |
| busstops/management/tests/test\_import\_nptg.py                 |       31 |        0 |    100% |           |
| busstops/management/tests/test\_import\_operators.py            |       64 |        0 |    100% |           |
| busstops/middleware.py                                          |       20 |        0 |    100% |           |
| busstops/models.py                                              |      613 |       30 |     95% |241, 287, 389, 426, 476, 502, 592, 631, 723, 787, 790-793, 804-805, 829-833, 838, 849, 868-869, 949-953, 1011, 1053, 1068, 1105 |
| busstops/templatetags/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| busstops/templatetags/date\_range.py                            |       25 |        3 |     88% | 9, 22, 28 |
| busstops/templatetags/urlise.py                                 |       17 |        0 |    100% |           |
| busstops/test\_admin.py                                         |       54 |        0 |    100% |           |
| busstops/test\_middleware.py                                    |       10 |        0 |    100% |           |
| busstops/test\_models.py                                        |      143 |        0 |    100% |           |
| busstops/test\_views.py                                         |      270 |        0 |    100% |           |
| busstops/urls.py                                                |       20 |        2 |     90% |   126-128 |
| busstops/utils.py                                               |        3 |        0 |    100% |           |
| busstops/views.py                                               |      623 |       57 |     91% |114, 134-138, 458, 484, 534, 698, 729, 793-796, 798, 912-917, 930, 1007, 1153, 1204-1205, 1210-1211, 1219-1228, 1245-1249, 1275-1302, 1361, 1388-1389, 1393-1396, 1546, 1558-1559, 1564, 1576-1577 |
| bustimes/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| bustimes/admin.py                                               |       97 |       12 |     88% |54, 60, 63-64, 67-68, 114-118, 141, 149, 162, 172 |
| bustimes/download\_utils.py                                     |       40 |        0 |    100% |           |
| bustimes/fields.py                                              |       31 |        1 |     97% |        12 |
| bustimes/formatting.py                                          |       19 |        0 |    100% |           |
| bustimes/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| bustimes/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| bustimes/management/commands/import\_atco\_cif.py               |      235 |       25 |     89% |28-35, 40, 43-44, 66, 198, 200, 203, 205, 213, 219, 283, 316-321, 361-362, 429 |
| bustimes/management/commands/import\_bod\_timetables.py         |      267 |       24 |     91% |47, 98, 102, 105-108, 113, 118-119, 139, 168, 178, 189, 257, 267-271, 287-289, 310, 326-327, 343 |
| bustimes/management/commands/import\_gtfs.py                    |      235 |       23 |     90% |75, 79, 129-130, 146, 215, 217, 277-278, 280-281, 317-318, 324-325, 329-332, 340-342, 390, 412 |
| bustimes/management/commands/import\_gtfs\_ember.py             |       89 |        0 |    100% |           |
| bustimes/management/commands/import\_gtfs\_flixbus.py           |      127 |        4 |     97% |93-95, 165 |
| bustimes/management/commands/import\_ni.py                      |       31 |        0 |    100% |           |
| bustimes/management/commands/import\_passenger.py               |      118 |       35 |     70% |51-54, 56-58, 102, 112-118, 146-179 |
| bustimes/management/commands/import\_tnds.py                    |       61 |        5 |     92% |46-48, 63-71 |
| bustimes/management/commands/import\_transxchange.py            |      775 |       75 |     90% |80, 92, 138-139, 363, 366-380, 409, 579-580, 617-618, 620-621, 644-645, 655, 663-664, 722, 733, 769, 795, 799-801, 855-859, 920, 924, 926, 942-947, 984-985, 996, 1013, 1021, 1023-1026, 1031, 1045, 1051, 1078, 1117, 1148-1149, 1177, 1181-1182, 1193, 1198, 1211, 1236, 1285-1286, 1315-1316, 1321, 1332 |
| bustimes/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_atco\_cif.py            |       70 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_bod.py                  |      226 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs.py                 |      106 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs\_ember\_flixbus.py |       75 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_ni.py                   |       21 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_passenger.py            |       23 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_transxchange.py         |      720 |        2 |     99% | 1076-1079 |
| bustimes/management/tests/test\_tnds.py                         |       22 |        0 |    100% |           |
| bustimes/models.py                                              |      320 |        6 |     98% |92, 343, 346, 375, 412, 446 |
| bustimes/tests.py                                               |      130 |        0 |    100% |           |
| bustimes/timetables.py                                          |      638 |       48 |     92% |62, 102-115, 144, 241-242, 259, 327-330, 342, 355-360, 406, 413, 481, 484, 500-503, 530, 639-654, 740-741, 812, 958-960 |
| bustimes/urls.py                                                |        3 |        0 |    100% |           |
| bustimes/utils.py                                               |      195 |       13 |     93% |171, 220, 246-248, 268-269, 292, 337, 354-355, 367, 403 |
| bustimes/views.py                                               |      372 |       80 |     78% |159-173, 182-184, 192-201, 203-211, 218, 240, 330, 339, 375, 381, 461, 511, 517, 542, 566-568, 585, 589-596, 601-624, 652-663, 672-678 |
| departures/\_\_init\_\_.py                                      |        0 |        0 |    100% |           |
| departures/avl.py                                               |       12 |        1 |     92% |        14 |
| departures/gtfsr.py                                             |       91 |        2 |     98% |   91, 111 |
| departures/live.py                                              |      134 |       14 |     90% |44, 59, 61, 63, 80-85, 145, 156, 168, 182 |
| departures/sources.py                                           |      216 |       33 |     85% |30, 54, 59, 63, 96, 112, 122, 125-127, 137-144, 149-150, 164-165, 173-174, 241, 308, 383, 387-388, 394-395, 398, 406 |
| departures/test\_gtfsr\_trip\_updates.py                        |       45 |        0 |    100% |           |
| departures/test\_gtfsr\_vehicle\_positions.py                   |       33 |        0 |    100% |           |
| departures/test\_live.py                                        |      111 |        0 |    100% |           |
| disruptions/\_\_init\_\_.py                                     |        0 |        0 |    100% |           |
| disruptions/admin.py                                            |       26 |        1 |     96% |        44 |
| disruptions/models.py                                           |       70 |        5 |     93% |41, 70, 94, 102, 112 |
| disruptions/siri\_sx.py                                         |      122 |       14 |     89% |50, 77, 89-92, 103-104, 135, 145-149 |
| disruptions/test\_siri\_sx.py                                   |       48 |        0 |    100% |           |
| disruptions/test\_tfl\_disruptions.py                           |       34 |        0 |    100% |           |
| disruptions/tests.py                                            |       16 |        0 |    100% |           |
| disruptions/tfl\_disruptions.py                                 |       85 |        2 |     98% |   63, 104 |
| disruptions/urls.py                                             |        3 |        0 |    100% |           |
| disruptions/views.py                                            |        9 |        0 |    100% |           |
| fares/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| fares/admin.py                                                  |       37 |        2 |     95% |    26, 29 |
| fares/forms.py                                                  |       26 |        3 |     88% | 17, 40-41 |
| fares/management/commands/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| fares/management/commands/import\_netex\_fares.py               |      353 |       59 |     83% |28, 69-70, 121, 128-130, 223-224, 323, 367-368, 449, 528-535, 555, 564-565, 583-588, 595-632, 652-653, 663-664, 670-679 |
| fares/management/commands/mytrip\_ticketing.py                  |       38 |        3 |     92% | 15, 44-45 |
| fares/models.py                                                 |      176 |        8 |     95% |60, 142, 217, 222, 245-246, 250-251 |
| fares/mytrip.py                                                 |       53 |        4 |     92% |35, 49-50, 73 |
| fares/test\_mytrip.py                                           |       40 |        0 |    100% |           |
| fares/tests.py                                                  |       79 |        0 |    100% |           |
| fares/urls.py                                                   |        3 |        0 |    100% |           |
| fares/views.py                                                  |       44 |        0 |    100% |           |
| manage.py                                                       |        6 |        0 |    100% |           |
| transxchange/\_\_init\_\_.py                                    |        0 |        0 |    100% |           |
| transxchange/test\_txc.py                                       |       23 |        0 |    100% |           |
| transxchange/txc.py                                             |      464 |       16 |     97% |42, 113, 160, 218, 246, 292-299, 396, 408, 470, 503-504, 662, 693 |
| vehicles/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| vehicles/admin.py                                               |      250 |       34 |     86% |32, 60, 87, 89, 182-183, 192, 205-206, 222, 251, 254, 277, 283, 285, 287, 290, 319, 337, 343, 381-396, 409, 422, 439, 488-490 |
| vehicles/apps.py                                                |        6 |        0 |    100% |           |
| vehicles/context\_processors.py                                 |       14 |        0 |    100% |           |
| vehicles/fields.py                                              |       37 |        0 |    100% |           |
| vehicles/filters.py                                             |       20 |        0 |    100% |           |
| vehicles/forms.py                                               |       93 |        3 |     97% |129, 167, 205 |
| vehicles/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| vehicles/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| vehicles/management/commands/import\_bod\_avl.py                |      476 |       56 |     88% |50, 128, 144, 153-154, 197-200, 203-206, 258, 274, 293-294, 317-335, 389, 395, 448, 451, 455, 461, 476-477, 524-537, 566, 575-576, 595, 624, 657, 775, 850, 854 |
| vehicles/management/commands/import\_bushub.py                  |       76 |       14 |     82% |22-23, 27-28, 31-32, 43, 46, 62-63, 72, 82, 101, 109 |
| vehicles/management/commands/import\_edinburgh.py               |       72 |        4 |     94% |83, 87-90, 97 |
| vehicles/management/commands/import\_gtfsr\_ember.py            |       86 |        7 |     92% |78-79, 102-104, 120, 141 |
| vehicles/management/commands/import\_gtfsr\_ie.py               |      102 |        6 |     94% |71, 98, 143, 152, 159, 163 |
| vehicles/management/commands/import\_live\_jersey.py            |       33 |        0 |    100% |           |
| vehicles/management/commands/import\_polar.py                   |       78 |       27 |     65% |13-14, 25, 28, 33-39, 45-47, 51, 55-56, 61-62, 65, 75-78, 81, 94, 101 |
| vehicles/management/commands/import\_stagecoach\_avl.py         |       94 |       15 |     84% |105, 116-127, 155, 162, 167-168, 179-185, 207-215 |
| vehicles/management/commands/siri\_vm\_subscribe.py             |       26 |        0 |    100% |           |
| vehicles/management/import\_live\_vehicles.py                   |      283 |       59 |     79% |38, 51-67, 80, 121, 130, 136-138, 162, 177, 181, 190-193, 202, 215, 223, 228, 232-233, 235-236, 241-242, 256-262, 294-295, 336, 339-340, 354-355, 370-371, 375, 398-399, 406-410, 427, 437-439 |
| vehicles/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| vehicles/management/tests/test\_bod\_avl.py                     |      314 |        0 |    100% |           |
| vehicles/management/tests/test\_bushub.py                       |       48 |        0 |    100% |           |
| vehicles/management/tests/test\_edinburgh.py                    |       51 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_live\_jersey.py         |       31 |        0 |    100% |           |
| vehicles/management/tests/test\_polar.py                        |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_siri\_post.py                   |       37 |        0 |    100% |           |
| vehicles/management/tests/test\_stagecoach\_avl.py              |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_stats.py                        |       24 |        0 |    100% |           |
| vehicles/models.py                                              |      505 |       32 |     94% |73, 189, 215, 281, 300, 306, 378, 384, 435, 456, 584-585, 598, 606, 623-625, 633-634, 637-638, 643-644, 667, 729, 736-739, 781, 794, 803, 814 |
| vehicles/rtpi.py                                                |       76 |        1 |     99% |        28 |
| vehicles/signals.py                                             |       11 |        0 |    100% |           |
| vehicles/tasks.py                                               |      130 |       24 |     82% |63-73, 80, 85, 95, 102-105, 108, 110, 119, 132, 136-137, 150, 164, 177-178, 232-233, 236 |
| vehicles/test\_models.py                                        |       65 |        0 |    100% |           |
| vehicles/test\_schedule\_adherence.py                           |       75 |        0 |    100% |           |
| vehicles/tests.py                                               |      438 |        0 |    100% |           |
| vehicles/time\_aware\_polyline.py                               |       56 |       48 |     14% |11, 18, 25, 36, 48-75, 79, 87-98, 106-120 |
| vehicles/urls.py                                                |        4 |        0 |    100% |           |
| vehicles/utils.py                                               |      128 |        6 |     95% |41-42, 155, 167-168, 172 |
| vehicles/views.py                                               |      589 |       60 |     90% |341-342, 393, 420, 435-436, 455-456, 482-483, 508-513, 518-519, 550, 568-569, 571, 576, 592-593, 611-630, 710-711, 718, 732, 840, 842, 844, 849, 894-895, 907-909, 995, 998-999, 1009, 1025-1030, 1070-1071, 1117, 1172-1211 |
| vosa/\_\_init\_\_.py                                            |        0 |        0 |    100% |           |
| vosa/admin.py                                                   |       36 |        0 |    100% |           |
| vosa/management/commands/\_\_init\_\_.py                        |        0 |        0 |    100% |           |
| vosa/management/commands/import\_vosa.py                        |      159 |        1 |     99% |       203 |
| vosa/models.py                                                  |       75 |        0 |    100% |           |
| vosa/tests.py                                                   |       60 |        0 |    100% |           |
| vosa/urls.py                                                    |        3 |        0 |    100% |           |
| vosa/views.py                                                   |       57 |        0 |    100% |           |
|                                                       **TOTAL** | **15748** | **1075** | **93%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/jclgoodwin/bustimes.org/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/jclgoodwin/bustimes.org/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fjclgoodwin%2Fbustimes.org%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.