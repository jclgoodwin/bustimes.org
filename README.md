# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| accounts/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| accounts/admin.py                                               |       41 |        0 |    100% |           |
| accounts/forms.py                                               |       50 |        0 |    100% |           |
| accounts/models.py                                              |       25 |        0 |    100% |           |
| accounts/tests.py                                               |      103 |        0 |    100% |           |
| accounts/urls.py                                                |        4 |        0 |    100% |           |
| accounts/views.py                                               |       62 |        1 |     98% |       110 |
| api/\_\_init\_\_.py                                             |        0 |        0 |    100% |           |
| api/api.py                                                      |       11 |        0 |    100% |           |
| api/filters.py                                                  |       62 |        5 |     92% |     57-61 |
| api/serializers.py                                              |      111 |        0 |    100% |           |
| api/tests.py                                                    |        9 |        0 |    100% |           |
| api/views.py                                                    |       93 |        0 |    100% |           |
| buses/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| buses/context\_processors.py                                    |        7 |        0 |    100% |           |
| buses/jinja2.py                                                 |       36 |        2 |     94% |    40, 61 |
| buses/settings.py                                               |      111 |       21 |     81% |96-104, 124, 207, 226-234, 251-267, 319 |
| buses/tests.py                                                  |        5 |        0 |    100% |           |
| buses/urls.py                                                   |        6 |        0 |    100% |           |
| buses/utils.py                                                  |       17 |        0 |    100% |           |
| busstops/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| busstops/admin.py                                               |      318 |       16 |     95% |102-108, 183, 242-250, 332-333, 379, 454, 458, 507, 540, 584, 588, 612, 616 |
| busstops/forms.py                                               |       46 |        0 |    100% |           |
| busstops/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| busstops/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| busstops/management/commands/import\_noc.py                     |      128 |        3 |     98% |155, 184, 243 |
| busstops/management/commands/naptan\_new.py                     |      143 |        5 |     97% |38, 91, 142, 202, 247 |
| busstops/management/commands/nptg\_new.py                       |       94 |        7 |     93% |148, 158, 163, 169-170, 172-173 |
| busstops/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| busstops/management/tests/test\_import\_ie.py                   |       63 |        0 |    100% |           |
| busstops/management/tests/test\_import\_naptan.py               |       67 |        0 |    100% |           |
| busstops/management/tests/test\_import\_nptg.py                 |       31 |        0 |    100% |           |
| busstops/management/tests/test\_import\_operators.py            |       64 |        0 |    100% |           |
| busstops/middleware.py                                          |       20 |        0 |    100% |           |
| busstops/models.py                                              |      619 |       25 |     96% |263, 309, 411, 448, 498, 524, 614, 653, 747, 811, 853-857, 862, 873, 892-893, 961, 973-977, 1035, 1077, 1092, 1129 |
| busstops/templatetags/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| busstops/templatetags/date\_range.py                            |       25 |        3 |     88% | 9, 22, 28 |
| busstops/templatetags/urlise.py                                 |       17 |        2 |     88% |     28-29 |
| busstops/test\_admin.py                                         |       52 |        0 |    100% |           |
| busstops/test\_middleware.py                                    |       10 |        0 |    100% |           |
| busstops/test\_models.py                                        |      143 |        0 |    100% |           |
| busstops/test\_views.py                                         |      271 |        0 |    100% |           |
| busstops/urls.py                                                |       20 |        2 |     90% |   136-138 |
| busstops/utils.py                                               |       11 |        0 |    100% |           |
| busstops/views.py                                               |      633 |       42 |     93% |114, 470, 496, 535, 721, 739, 803-806, 808, 922-927, 940, 1017, 1045-1046, 1051-1052, 1060-1069, 1220, 1261-1265, 1308, 1387, 1419-1420, 1424-1427, 1579, 1591-1592, 1597, 1609-1610 |
| bustimes/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| bustimes/admin.py                                               |      105 |       15 |     86% |57, 60-61, 67, 70-71, 74-75, 122-126, 149, 157, 170, 173, 184 |
| bustimes/download\_utils.py                                     |       32 |        0 |    100% |           |
| bustimes/fields.py                                              |       31 |        1 |     97% |        12 |
| bustimes/formatting.py                                          |       19 |        0 |    100% |           |
| bustimes/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| bustimes/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| bustimes/management/commands/bank\_holidays.py                  |       52 |        1 |     98% |       102 |
| bustimes/management/commands/import\_atco\_cif.py               |      235 |       25 |     89% |28-35, 40, 43-44, 66, 198, 200, 203, 205, 213, 219, 283, 316-321, 361-362, 429 |
| bustimes/management/commands/import\_bod\_timetables.py         |      272 |       24 |     91% |46, 97, 101, 104-107, 112, 117-118, 138, 169, 179, 190, 259, 269-273, 289-291, 314, 330-331, 348 |
| bustimes/management/commands/import\_gtfs.py                    |      235 |       22 |     91% |75, 79, 129-130, 146, 218, 220, 280-281, 283-284, 320-321, 327-328, 332-335, 343-345, 414 |
| bustimes/management/commands/import\_gtfs\_ember.py             |       91 |        0 |    100% |           |
| bustimes/management/commands/import\_gtfs\_flixbus.py           |      143 |        3 |     98% |75, 140, 206 |
| bustimes/management/commands/import\_ni.py                      |       31 |        0 |    100% |           |
| bustimes/management/commands/import\_passenger.py               |      118 |       35 |     70% |51-54, 56-58, 102, 112-118, 146-179 |
| bustimes/management/commands/import\_tnds.py                    |       61 |        5 |     92% |46-48, 63-71 |
| bustimes/management/commands/import\_transxchange.py            |      773 |       76 |     90% |83, 95, 141-142, 368, 371-385, 414, 546, 588-589, 626-627, 629-630, 653-654, 664, 672-673, 731, 742, 778, 804, 808-810, 864-868, 929, 933, 935, 948-953, 990-991, 1002, 1019, 1027, 1029-1032, 1055, 1082, 1121, 1152-1153, 1180-1182, 1189, 1194-1195, 1206, 1211, 1224, 1249, 1283-1284, 1319-1320, 1387 |
| bustimes/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| bustimes/management/tests/test\_bank\_holidays.py               |       20 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_atco\_cif.py            |       70 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_bod.py                  |      233 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs.py                 |      103 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs\_ember\_flixbus.py |       75 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_ni.py                   |       21 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_passenger.py            |       23 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_transxchange.py         |      729 |        0 |    100% |           |
| bustimes/management/tests/test\_tnds.py                         |       22 |        0 |    100% |           |
| bustimes/models.py                                              |      326 |        6 |     98% |103, 361, 364, 393, 430, 464 |
| bustimes/tests.py                                               |      130 |        0 |    100% |           |
| bustimes/timetables.py                                          |      637 |       53 |     92% |62, 102-115, 144, 226-237, 268-269, 341-344, 356, 369-374, 388, 407, 482, 485, 501-504, 506, 533, 642-657, 743-744, 815, 961-963 |
| bustimes/urls.py                                                |        3 |        0 |    100% |           |
| bustimes/utils.py                                               |      195 |       11 |     94% |220, 246-248, 268-269, 337, 354-355, 367, 403 |
| bustimes/views.py                                               |      372 |       75 |     80% |161-175, 184-186, 194-203, 205-213, 220, 242, 332, 341, 377, 383, 463, 567, 591-593, 610, 614-642, 670-681, 690-696 |
| departures/\_\_init\_\_.py                                      |        0 |        0 |    100% |           |
| departures/avl.py                                               |       12 |        1 |     92% |        14 |
| departures/gtfsr.py                                             |       91 |        2 |     98% |   91, 111 |
| departures/live.py                                              |      134 |       14 |     90% |44, 59, 61, 63, 80-85, 145, 156, 168, 182 |
| departures/sources.py                                           |      216 |       33 |     85% |30, 54, 59, 63, 96, 112, 122, 125-127, 137-144, 149-150, 164-165, 173-174, 241, 309, 384, 388-389, 395-396, 399, 407 |
| departures/test\_gtfsr\_trip\_updates.py                        |       45 |        0 |    100% |           |
| departures/test\_gtfsr\_vehicle\_positions.py                   |       33 |        0 |    100% |           |
| departures/test\_live.py                                        |      111 |        0 |    100% |           |
| disruptions/\_\_init\_\_.py                                     |        0 |        0 |    100% |           |
| disruptions/admin.py                                            |       26 |        1 |     96% |        44 |
| disruptions/models.py                                           |       71 |        5 |     93% |42, 71, 95, 103, 113 |
| disruptions/siri\_sx.py                                         |      122 |       14 |     89% |50, 77, 89-92, 103-104, 135, 145-149 |
| disruptions/test\_siri\_sx.py                                   |       48 |        0 |    100% |           |
| disruptions/test\_tfl\_disruptions.py                           |       34 |        0 |    100% |           |
| disruptions/tests.py                                            |       16 |        0 |    100% |           |
| disruptions/tfl\_disruptions.py                                 |       85 |        2 |     98% |   63, 104 |
| disruptions/urls.py                                             |        3 |        0 |    100% |           |
| disruptions/views.py                                            |        9 |        0 |    100% |           |
| fares/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| fares/admin.py                                                  |       37 |        2 |     95% |    26, 29 |
| fares/forms.py                                                  |       26 |        3 |     88% | 18, 41-42 |
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
| transxchange/txc.py                                             |      467 |       16 |     97% |42, 113, 160, 218, 246, 292-299, 398, 410, 472, 505-506, 661, 692 |
| vehicles/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| vehicles/admin.py                                               |      249 |       34 |     86% |32, 60, 87, 89, 182-183, 192, 205-206, 222, 251, 254, 277, 283, 285, 287, 290, 319, 335, 341, 402-417, 430, 443, 460, 503-505 |
| vehicles/apps.py                                                |        6 |        0 |    100% |           |
| vehicles/context\_processors.py                                 |       14 |        0 |    100% |           |
| vehicles/fields.py                                              |       23 |        0 |    100% |           |
| vehicles/filters.py                                             |       20 |        0 |    100% |           |
| vehicles/form\_fields.py                                        |       15 |        0 |    100% |           |
| vehicles/forms.py                                               |       94 |        3 |     97% |130, 168, 206 |
| vehicles/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| vehicles/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| vehicles/management/commands/import\_aircoach.py                |        6 |        0 |    100% |           |
| vehicles/management/commands/import\_bod\_avl.py                |      466 |       54 |     88% |51, 129, 145, 155-156, 199-202, 205-208, 251, 267, 282-283, 305-323, 377, 383, 437, 443, 458-459, 506-519, 548, 557-558, 577, 606, 636, 754, 829, 833 |
| vehicles/management/commands/import\_bushub.py                  |       72 |       14 |     81% |16-17, 21-22, 25-26, 37, 40, 56-57, 66, 76, 95, 103 |
| vehicles/management/commands/import\_edinburgh.py               |       72 |        4 |     94% |83, 87-90, 97 |
| vehicles/management/commands/import\_gtfsr\_ember.py            |       85 |        6 |     93% |78-79, 102-104, 120 |
| vehicles/management/commands/import\_gtfsr\_ie.py               |      104 |        6 |     94% |71, 98, 145, 154, 161, 165 |
| vehicles/management/commands/import\_live\_jersey.py            |       33 |        0 |    100% |           |
| vehicles/management/commands/import\_megabus.py                 |      118 |       29 |     75% |38-40, 42-43, 46-47, 64, 72-75, 79-82, 119-122, 125, 145-146, 148-149, 151-152, 162, 173 |
| vehicles/management/commands/import\_natexp.py                  |        6 |        0 |    100% |           |
| vehicles/management/commands/import\_nx.py                      |      100 |       16 |     84% |84-86, 88-89, 107-112, 132-137, 154-155 |
| vehicles/management/commands/import\_polar.py                   |       75 |       25 |     67% |13-14, 25, 28, 33-39, 45-47, 51, 61-62, 65, 79-82, 85, 98, 105 |
| vehicles/management/commands/import\_stagecoach\_avl.py         |       94 |       15 |     84% |105, 116-127, 155, 162, 167-168, 179-185, 207-215 |
| vehicles/management/commands/siri\_vm\_subscribe.py             |       26 |        7 |     73% |     27-55 |
| vehicles/management/import\_live\_vehicles.py                   |      283 |       59 |     79% |38, 51-67, 80, 121, 130, 136-138, 162, 177, 181, 190-193, 202, 215, 223, 228, 232-233, 235-236, 241-242, 256-262, 294-295, 336, 339-340, 354-355, 370-371, 375, 398-399, 406-410, 427, 437-439 |
| vehicles/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| vehicles/management/tests/test\_bod\_avl.py                     |      311 |        0 |    100% |           |
| vehicles/management/tests/test\_bushub.py                       |       48 |        0 |    100% |           |
| vehicles/management/tests/test\_edinburgh.py                    |       51 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_live\_jersey.py         |       31 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_nx.py                   |       77 |        0 |    100% |           |
| vehicles/management/tests/test\_polar.py                        |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_siri\_post.py                   |       40 |        0 |    100% |           |
| vehicles/management/tests/test\_stagecoach\_avl.py              |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_stats.py                        |       24 |        0 |    100% |           |
| vehicles/models.py                                              |      503 |       35 |     93% |75, 191, 216, 282, 301, 307, 379, 385, 436, 457, 572-573, 586, 594, 611-613, 621-622, 625-626, 631-632, 655, 676-680, 731-734, 789, 798, 809 |
| vehicles/rtpi.py                                                |       76 |        1 |     99% |        28 |
| vehicles/signals.py                                             |       11 |        0 |    100% |           |
| vehicles/tasks.py                                               |      132 |       20 |     85% |80, 85, 95, 102-105, 108, 110, 119, 132, 136-137, 155, 169, 182-183, 237-238, 241 |
| vehicles/test\_models.py                                        |       62 |        0 |    100% |           |
| vehicles/test\_schedule\_adherence.py                           |       75 |        0 |    100% |           |
| vehicles/tests.py                                               |      439 |        0 |    100% |           |
| vehicles/time\_aware\_polyline.py                               |       56 |       28 |     50% |18, 36, 49, 54, 57, 87-98, 106-120 |
| vehicles/urls.py                                                |        4 |        0 |    100% |           |
| vehicles/utils.py                                               |      128 |        6 |     95% |41-42, 155, 167-168, 172 |
| vehicles/views.py                                               |      592 |       60 |     90% |344-345, 396, 423, 438-439, 458-459, 485-486, 511-516, 521-522, 553, 571-572, 574, 579, 595-596, 614-633, 713-714, 721, 735, 843, 845, 847, 852, 897-898, 910-912, 999, 1002-1003, 1013, 1029-1034, 1075-1076, 1122, 1183-1221 |
| vosa/\_\_init\_\_.py                                            |        0 |        0 |    100% |           |
| vosa/admin.py                                                   |       36 |        0 |    100% |           |
| vosa/management/commands/\_\_init\_\_.py                        |        0 |        0 |    100% |           |
| vosa/management/commands/import\_vosa.py                        |      162 |        3 |     98% |25-26, 206 |
| vosa/models.py                                                  |       75 |        0 |    100% |           |
| vosa/tests.py                                                   |       60 |        0 |    100% |           |
| vosa/urls.py                                                    |        3 |        0 |    100% |           |
| vosa/views.py                                                   |       57 |        0 |    100% |           |
|                                                       **TOTAL** | **16166** | **1078** | **93%** |           |


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