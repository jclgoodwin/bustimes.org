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
| api/filters.py                                                  |       63 |        5 |     92% |     55-59 |
| api/serializers.py                                              |      111 |        4 |     96% |   220-223 |
| api/tests.py                                                    |        9 |        0 |    100% |           |
| api/views.py                                                    |       93 |        0 |    100% |           |
| buses/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| buses/context\_processors.py                                    |        7 |        0 |    100% |           |
| buses/jinja2.py                                                 |       36 |        2 |     94% |    40, 61 |
| buses/settings.py                                               |      122 |       30 |     75% |95-103, 123, 142-150, 206, 225-233, 250-266, 318 |
| buses/tests.py                                                  |        5 |        0 |    100% |           |
| buses/urls.py                                                   |        5 |        0 |    100% |           |
| buses/utils.py                                                  |       17 |        0 |    100% |           |
| busstops/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| busstops/admin.py                                               |      318 |       16 |     95% |103-109, 184, 243-251, 333-334, 380, 455, 459, 508, 542, 586, 590, 614, 618 |
| busstops/forms.py                                               |       46 |        0 |    100% |           |
| busstops/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| busstops/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| busstops/management/commands/import\_noc.py                     |      125 |        3 |     98% |155, 179, 238 |
| busstops/management/commands/naptan\_new.py                     |      151 |        3 |     98% |145, 213, 258 |
| busstops/management/commands/nptg\_new.py                       |       94 |        7 |     93% |148, 158, 163, 169-170, 172-173 |
| busstops/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| busstops/management/tests/test\_import\_ie.py                   |       63 |        0 |    100% |           |
| busstops/management/tests/test\_import\_naptan.py               |       67 |        0 |    100% |           |
| busstops/management/tests/test\_import\_nptg.py                 |       31 |        0 |    100% |           |
| busstops/management/tests/test\_import\_operators.py            |       64 |        0 |    100% |           |
| busstops/middleware.py                                          |       28 |        7 |     75% |     29-43 |
| busstops/models.py                                              |      627 |       24 |     96% |275, 321, 423, 460, 510, 536, 626, 665, 759, 823, 865-869, 874, 885, 904-905, 973, 985-989, 1089, 1104, 1141 |
| busstops/templatetags/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| busstops/templatetags/date\_range.py                            |       25 |        3 |     88% | 9, 22, 28 |
| busstops/templatetags/urlise.py                                 |       16 |        0 |    100% |           |
| busstops/test\_admin.py                                         |       52 |        0 |    100% |           |
| busstops/test\_middleware.py                                    |       10 |        0 |    100% |           |
| busstops/test\_models.py                                        |      143 |        0 |    100% |           |
| busstops/test\_views.py                                         |      270 |        0 |    100% |           |
| busstops/urls.py                                                |       20 |        2 |     90% |   136-138 |
| busstops/utils.py                                               |       11 |        0 |    100% |           |
| busstops/views.py                                               |      637 |       49 |     92% |121, 162-171, 478, 504, 543, 729, 747, 811-814, 816, 949-954, 967, 1044, 1072-1073, 1078-1079, 1087-1096, 1247, 1268, 1270, 1296-1300, 1349, 1422, 1452-1453, 1456-1460, 1612, 1624-1625, 1630, 1642-1643 |
| bustimes/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| bustimes/admin.py                                               |      113 |       15 |     87% |64, 67-68, 74, 77-78, 81-82, 139-143, 166, 174, 187, 190, 201 |
| bustimes/download\_utils.py                                     |       32 |        0 |    100% |           |
| bustimes/fields.py                                              |       31 |        1 |     97% |        12 |
| bustimes/formatting.py                                          |       19 |        0 |    100% |           |
| bustimes/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| bustimes/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| bustimes/management/commands/bank\_holidays.py                  |       52 |        1 |     98% |       102 |
| bustimes/management/commands/import\_atco\_cif.py               |      235 |       25 |     89% |28-35, 40, 43-44, 66, 198, 200, 203, 205, 213, 219, 283, 316-321, 361-362, 429 |
| bustimes/management/commands/import\_bod\_timetables.py         |      268 |       24 |     91% |47, 96, 100, 103-106, 111, 116-117, 137, 168, 178, 189, 258, 268-272, 288-290, 313, 329-330, 346 |
| bustimes/management/commands/import\_gtfs.py                    |      239 |       23 |     90% |78, 82, 132-133, 145, 152, 224, 226, 286-287, 289-290, 326-327, 333-334, 338-341, 349-351, 420 |
| bustimes/management/commands/import\_gtfs\_ember.py             |      103 |        6 |     94% |66-67, 82, 125, 130, 166 |
| bustimes/management/commands/import\_gtfs\_flixbus.py           |      144 |        3 |     98% |75, 142, 208 |
| bustimes/management/commands/import\_ni.py                      |       31 |        0 |    100% |           |
| bustimes/management/commands/import\_passenger.py               |      116 |       34 |     71% |51-54, 56-58, 102, 112-116, 142-179 |
| bustimes/management/commands/import\_tnds.py                    |       43 |        0 |    100% |           |
| bustimes/management/commands/import\_transxchange.py            |      779 |       76 |     90% |84, 96, 142-143, 291, 374-388, 417, 542, 584-585, 622-623, 625-626, 649-650, 660, 668-669, 727, 738, 774, 800, 804-806, 860-864, 925, 929, 931, 944-949, 986-987, 998, 1015, 1023, 1025-1028, 1051, 1078, 1117, 1148-1149, 1176-1178, 1185, 1190-1191, 1202, 1207, 1220, 1245, 1279-1280, 1316-1317, 1386 |
| bustimes/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| bustimes/management/tests/test\_bank\_holidays.py               |       20 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_atco\_cif.py            |       70 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_bod.py                  |      242 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs.py                 |      103 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs\_ember\_flixbus.py |       78 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_ni.py                   |       21 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_passenger.py            |       23 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_transxchange.py         |      742 |        0 |    100% |           |
| bustimes/management/tests/test\_tnds.py                         |       19 |        0 |    100% |           |
| bustimes/models.py                                              |      340 |        8 |     98% |111, 372, 375, 404, 449-452, 484 |
| bustimes/test\_get\_trip.py                                     |       31 |        0 |    100% |           |
| bustimes/tests.py                                               |      132 |        0 |    100% |           |
| bustimes/timetables.py                                          |      637 |       53 |     92% |102-115, 144, 226-237, 268-269, 329, 341-344, 356, 369-374, 388, 407, 482, 485, 501-504, 506, 533, 642-657, 743-744, 815, 961-963 |
| bustimes/urls.py                                                |        3 |        0 |    100% |           |
| bustimes/utils.py                                               |      186 |       10 |     95% |219, 245-247, 267-268, 337, 354-355, 403 |
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
| disruptions/admin.py                                            |       26 |        1 |     96% |        53 |
| disruptions/models.py                                           |       72 |        5 |     93% |43, 72, 96, 104, 114 |
| disruptions/siri\_sx.py                                         |      122 |       14 |     89% |58, 78, 90-93, 104-105, 136, 146-150 |
| disruptions/test\_siri\_sx.py                                   |       48 |        0 |    100% |           |
| disruptions/test\_tfl\_disruptions.py                           |       34 |        0 |    100% |           |
| disruptions/tests.py                                            |       16 |        0 |    100% |           |
| disruptions/tfl\_disruptions.py                                 |       91 |        2 |     98% |    49, 85 |
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
| transxchange/txc.py                                             |      481 |       18 |     96% |50, 121, 168, 228, 256, 302-309, 376, 378, 422, 443, 505, 538-539, 694, 725 |
| vehicles/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| vehicles/admin.py                                               |      249 |       34 |     86% |32, 60, 87, 89, 182-183, 192, 205-206, 222, 251, 254, 277, 283, 285, 287, 290, 319, 335, 341, 404-419, 432, 445, 462, 505-507 |
| vehicles/apps.py                                                |        6 |        0 |    100% |           |
| vehicles/context\_processors.py                                 |       14 |        0 |    100% |           |
| vehicles/fields.py                                              |       23 |        0 |    100% |           |
| vehicles/filters.py                                             |       20 |        0 |    100% |           |
| vehicles/form\_fields.py                                        |       15 |        0 |    100% |           |
| vehicles/forms.py                                               |       94 |        3 |     97% |130, 168, 206 |
| vehicles/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| vehicles/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| vehicles/management/commands/import\_bod\_avl.py                |      449 |       55 |     88% |56, 133, 149, 159-160, 203-206, 209-212, 255, 271, 286-287, 309-327, 378, 380, 386, 417, 423, 438-439, 483-496, 524, 537-538, 557, 586, 616, 734, 809, 813 |
| vehicles/management/commands/import\_bushub.py                  |       72 |       14 |     81% |16-17, 21-22, 25-26, 37, 40, 56-57, 66, 76, 95, 103 |
| vehicles/management/commands/import\_edinburgh.py               |       72 |        4 |     94% |83, 87-90, 97 |
| vehicles/management/commands/import\_gtfsr\_ember.py            |       87 |        6 |     93% |81-82, 105-107, 123 |
| vehicles/management/commands/import\_gtfsr\_ie.py               |      105 |        6 |     94% |83, 110, 157, 166, 173, 177 |
| vehicles/management/commands/import\_live\_jersey.py            |       35 |        0 |    100% |           |
| vehicles/management/commands/import\_nx.py                      |      137 |       27 |     80% |47, 91, 108-110, 112-113, 116-117, 134, 142-145, 149-152, 168-171, 174, 186-187, 197, 208 |
| vehicles/management/commands/import\_polar.py                   |       75 |       25 |     67% |13-14, 25, 28, 33-39, 45-47, 51, 61-62, 65, 79-82, 85, 98, 105 |
| vehicles/management/commands/import\_stagecoach\_avl.py         |       94 |       15 |     84% |105, 116-127, 155, 162, 167-168, 179-185, 207-215 |
| vehicles/management/commands/signalr.py                         |       66 |        5 |     92% |58, 75-77, 89 |
| vehicles/management/commands/siri\_vm\_subscribe.py             |       26 |        7 |     73% |     27-55 |
| vehicles/management/import\_live\_vehicles.py                   |      283 |       58 |     80% |38, 51-67, 121, 130, 136-138, 162, 177, 181, 190-193, 202, 215, 223, 228, 232-233, 235-236, 241-242, 256-262, 294-295, 336, 339-340, 354-355, 370-371, 375, 398-399, 406-410, 427, 437-439 |
| vehicles/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| vehicles/management/tests/test\_bod\_avl.py                     |      294 |        0 |    100% |           |
| vehicles/management/tests/test\_bushub.py                       |       48 |        0 |    100% |           |
| vehicles/management/tests/test\_edinburgh.py                    |       51 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_live\_jersey.py         |       31 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_nx.py                   |       43 |        0 |    100% |           |
| vehicles/management/tests/test\_polar.py                        |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_signalr.py                      |       22 |        0 |    100% |           |
| vehicles/management/tests/test\_siri\_post.py                   |       40 |        0 |    100% |           |
| vehicles/management/tests/test\_stagecoach\_avl.py              |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_stats.py                        |       24 |        0 |    100% |           |
| vehicles/models.py                                              |      497 |       37 |     93% |75, 191, 216, 282, 301, 307, 379, 385, 436, 457, 572-573, 586, 594, 611-613, 621-622, 625-626, 631-632, 657, 678-682, 713, 720-723, 765, 778, 787, 798 |
| vehicles/rtpi.py                                                |       76 |        1 |     99% |        28 |
| vehicles/signals.py                                             |       11 |        0 |    100% |           |
| vehicles/tasks.py                                               |      132 |       20 |     85% |80, 85, 95, 102-105, 108, 110, 119, 132, 136-137, 155, 169, 182-183, 237-238, 241 |
| vehicles/test\_models.py                                        |       62 |        0 |    100% |           |
| vehicles/test\_schedule\_adherence.py                           |       75 |        0 |    100% |           |
| vehicles/tests.py                                               |      435 |        0 |    100% |           |
| vehicles/time\_aware\_polyline.py                               |       56 |       28 |     50% |18, 36, 49, 54, 57, 87-98, 106-120 |
| vehicles/urls.py                                                |        4 |        0 |    100% |           |
| vehicles/utils.py                                               |      128 |        6 |     95% |41-42, 155, 167-168, 172 |
| vehicles/views.py                                               |      598 |       61 |     90% |344-345, 396, 423, 438-439, 458-459, 472, 490-491, 516-521, 526-527, 558, 576-577, 579, 584, 600-601, 619-638, 718-719, 726, 740, 848, 850, 852, 857, 902-903, 915-917, 1004, 1007-1008, 1018, 1034-1039, 1080-1081, 1127, 1195-1233 |
| vosa/\_\_init\_\_.py                                            |        0 |        0 |    100% |           |
| vosa/admin.py                                                   |       36 |        0 |    100% |           |
| vosa/management/commands/\_\_init\_\_.py                        |        0 |        0 |    100% |           |
| vosa/management/commands/import\_vosa.py                        |      162 |        3 |     98% |25-26, 206 |
| vosa/models.py                                                  |       75 |        0 |    100% |           |
| vosa/tests.py                                                   |       60 |        0 |    100% |           |
| vosa/urls.py                                                    |        3 |        0 |    100% |           |
| vosa/views.py                                                   |       57 |        0 |    100% |           |
|                                                       **TOTAL** | **16216** | **1094** | **93%** |           |


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