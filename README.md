# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| accounts/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| accounts/admin.py                                               |       41 |        0 |    100% |           |
| accounts/forms.py                                               |       50 |        0 |    100% |           |
| accounts/models.py                                              |       25 |        0 |    100% |           |
| accounts/tests.py                                               |      101 |        0 |    100% |           |
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
| busstops/models.py                                              |      613 |       31 |     95% |241, 287, 389, 426, 476, 502, 592, 631, 723, 787, 790-793, 804-805, 829-833, 838, 849, 868-869, 937, 949-953, 1011, 1053, 1068, 1105 |
| busstops/templatetags/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| busstops/templatetags/date\_range.py                            |       25 |        3 |     88% | 9, 22, 28 |
| busstops/templatetags/urlise.py                                 |       14 |        0 |    100% |           |
| busstops/test\_admin.py                                         |       53 |        0 |    100% |           |
| busstops/test\_middleware.py                                    |       10 |        0 |    100% |           |
| busstops/test\_models.py                                        |      143 |        0 |    100% |           |
| busstops/test\_views.py                                         |      271 |        0 |    100% |           |
| busstops/urls.py                                                |       20 |        2 |     90% |   136-138 |
| busstops/utils.py                                               |        3 |        0 |    100% |           |
| busstops/views.py                                               |      627 |       42 |     93% |114, 470, 496, 535, 721, 739, 803-806, 808, 918-923, 936, 1013, 1041-1042, 1047-1048, 1056-1065, 1216, 1247-1251, 1294, 1366, 1393-1394, 1398-1401, 1551, 1563-1564, 1569, 1581-1582 |
| bustimes/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| bustimes/admin.py                                               |       98 |       12 |     88% |54, 60, 63-64, 67-68, 115-119, 142, 150, 163, 173 |
| bustimes/download\_utils.py                                     |       32 |        0 |    100% |           |
| bustimes/fields.py                                              |       31 |        1 |     97% |        12 |
| bustimes/formatting.py                                          |       19 |        0 |    100% |           |
| bustimes/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| bustimes/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| bustimes/management/commands/import\_atco\_cif.py               |      235 |       25 |     89% |28-35, 40, 43-44, 66, 198, 200, 203, 205, 213, 219, 283, 316-321, 361-362, 429 |
| bustimes/management/commands/import\_bod\_timetables.py         |      269 |       24 |     91% |46, 97, 101, 104-107, 112, 117-118, 138, 169, 179, 190, 258, 268-272, 288-290, 313, 329-330, 346 |
| bustimes/management/commands/import\_gtfs.py                    |      234 |       22 |     91% |75, 79, 129-130, 146, 215, 217, 277-278, 280-281, 317-318, 324-325, 329-332, 340-342, 411 |
| bustimes/management/commands/import\_gtfs\_ember.py             |       89 |        0 |    100% |           |
| bustimes/management/commands/import\_gtfs\_flixbus.py           |      142 |        2 |     99% |  138, 203 |
| bustimes/management/commands/import\_ni.py                      |       31 |        0 |    100% |           |
| bustimes/management/commands/import\_passenger.py               |      118 |       35 |     70% |51-54, 56-58, 102, 112-118, 146-179 |
| bustimes/management/commands/import\_tnds.py                    |       61 |        5 |     92% |46-48, 63-71 |
| bustimes/management/commands/import\_transxchange.py            |      778 |       74 |     90% |82, 94, 140-141, 365, 368-382, 411, 581-582, 619-620, 622-623, 646-647, 657, 665-666, 724, 735, 771, 797, 801-803, 857-861, 922, 926, 928, 944-949, 986-987, 998, 1015, 1023, 1025-1028, 1051, 1078, 1117, 1148-1149, 1176-1178, 1185, 1190-1191, 1202, 1207, 1220, 1245, 1294-1295, 1324-1325 |
| bustimes/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_atco\_cif.py            |       70 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_bod.py                  |      232 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs.py                 |      103 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs\_ember\_flixbus.py |       75 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_ni.py                   |       21 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_passenger.py            |       23 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_transxchange.py         |      729 |        2 |     99% | 1076-1079 |
| bustimes/management/tests/test\_tnds.py                         |       22 |        0 |    100% |           |
| bustimes/models.py                                              |      320 |        7 |     98% |92, 185, 343, 346, 375, 412, 446 |
| bustimes/tests.py                                               |      130 |        0 |    100% |           |
| bustimes/timetables.py                                          |      637 |       53 |     92% |62, 102-115, 144, 226-237, 268-269, 341-344, 356, 369-374, 388, 407, 482, 485, 501-504, 506, 533, 642-657, 743-744, 815, 961-963 |
| bustimes/urls.py                                                |        3 |        0 |    100% |           |
| bustimes/utils.py                                               |      195 |       12 |     94% |219, 245-247, 267-268, 291, 336, 353-354, 366, 402 |
| bustimes/views.py                                               |      372 |       75 |     80% |161-175, 184-186, 194-203, 205-213, 220, 242, 332, 341, 377, 383, 463, 567, 591-593, 610, 614-642, 670-681, 690-696 |
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
| vehicles/admin.py                                               |      253 |       34 |     87% |32, 60, 87, 89, 182-183, 192, 205-206, 222, 251, 254, 277, 283, 285, 287, 290, 319, 335, 341, 402-417, 430, 443, 460, 509-511 |
| vehicles/apps.py                                                |        6 |        0 |    100% |           |
| vehicles/context\_processors.py                                 |       14 |        0 |    100% |           |
| vehicles/fields.py                                              |       23 |        0 |    100% |           |
| vehicles/filters.py                                             |       20 |        0 |    100% |           |
| vehicles/form\_fields.py                                        |       15 |        0 |    100% |           |
| vehicles/forms.py                                               |       94 |        3 |     97% |130, 168, 206 |
| vehicles/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| vehicles/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| vehicles/management/commands/import\_bod\_avl.py                |      470 |       53 |     89% |52, 130, 146, 156-157, 200-203, 206-209, 252, 268, 283-284, 306-324, 378, 384, 437, 469-470, 517-530, 559, 568-569, 588, 617, 647, 765, 840, 844 |
| vehicles/management/commands/import\_bushub.py                  |       76 |       14 |     82% |22-23, 27-28, 31-32, 43, 46, 62-63, 72, 82, 101, 109 |
| vehicles/management/commands/import\_edinburgh.py               |       72 |        4 |     94% |83, 87-90, 97 |
| vehicles/management/commands/import\_gtfsr\_ember.py            |       86 |        7 |     92% |78-79, 102-104, 120, 141 |
| vehicles/management/commands/import\_gtfsr\_ie.py               |      104 |        6 |     94% |71, 98, 145, 154, 161, 165 |
| vehicles/management/commands/import\_live\_jersey.py            |       33 |        0 |    100% |           |
| vehicles/management/commands/import\_polar.py                   |       75 |       25 |     67% |13-14, 25, 28, 33-39, 45-47, 51, 61-62, 65, 79-82, 85, 98, 105 |
| vehicles/management/commands/import\_stagecoach\_avl.py         |       94 |       15 |     84% |105, 116-127, 155, 162, 167-168, 179-185, 207-215 |
| vehicles/management/commands/siri\_vm\_subscribe.py             |       26 |        7 |     73% |     27-55 |
| vehicles/management/import\_live\_vehicles.py                   |      283 |       58 |     80% |38, 51-67, 80, 121, 130, 136-138, 177, 181, 190-193, 202, 215, 223, 228, 232-233, 235-236, 241-242, 256-262, 294-295, 336, 339-340, 354-355, 370-371, 375, 398-399, 406-410, 427, 437-439 |
| vehicles/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| vehicles/management/tests/test\_bod\_avl.py                     |      317 |        0 |    100% |           |
| vehicles/management/tests/test\_bushub.py                       |       48 |        0 |    100% |           |
| vehicles/management/tests/test\_edinburgh.py                    |       51 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_live\_jersey.py         |       31 |        0 |    100% |           |
| vehicles/management/tests/test\_polar.py                        |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_siri\_post.py                   |       40 |        0 |    100% |           |
| vehicles/management/tests/test\_stagecoach\_avl.py              |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_stats.py                        |       24 |        0 |    100% |           |
| vehicles/models.py                                              |      511 |       37 |     93% |75, 191, 217, 283, 302, 308, 380, 386, 437, 458, 586-587, 600, 608, 625-627, 635-636, 639-640, 645-646, 669, 690-694, 738, 745-748, 790, 803, 812, 823 |
| vehicles/rtpi.py                                                |       76 |        1 |     99% |        28 |
| vehicles/signals.py                                             |       11 |        0 |    100% |           |
| vehicles/tasks.py                                               |      132 |       20 |     85% |80, 85, 95, 102-105, 108, 110, 119, 132, 136-137, 155, 169, 182-183, 237-238, 241 |
| vehicles/test\_models.py                                        |       65 |        0 |    100% |           |
| vehicles/test\_schedule\_adherence.py                           |       75 |        0 |    100% |           |
| vehicles/tests.py                                               |      438 |        0 |    100% |           |
| vehicles/time\_aware\_polyline.py                               |       56 |       28 |     50% |18, 36, 49, 54, 57, 87-98, 106-120 |
| vehicles/urls.py                                                |        4 |        0 |    100% |           |
| vehicles/utils.py                                               |      128 |        6 |     95% |41-42, 155, 167-168, 172 |
| vehicles/views.py                                               |      592 |       60 |     90% |344-345, 396, 423, 438-439, 458-459, 485-486, 511-516, 521-522, 553, 571-572, 574, 579, 595-596, 614-633, 713-714, 721, 735, 843, 845, 847, 852, 897-898, 910-912, 999, 1002-1003, 1013, 1029-1034, 1075-1076, 1122, 1183-1222 |
| vosa/\_\_init\_\_.py                                            |        0 |        0 |    100% |           |
| vosa/admin.py                                                   |       36 |        0 |    100% |           |
| vosa/management/commands/\_\_init\_\_.py                        |        0 |        0 |    100% |           |
| vosa/management/commands/import\_vosa.py                        |      162 |        3 |     98% |25-26, 206 |
| vosa/models.py                                                  |       75 |        0 |    100% |           |
| vosa/tests.py                                                   |       60 |        0 |    100% |           |
| vosa/urls.py                                                    |        3 |        0 |    100% |           |
| vosa/views.py                                                   |       57 |        0 |    100% |           |
|                                                       **TOTAL** | **15789** | **1035** | **93%** |           |


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