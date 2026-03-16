# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| accounts/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| accounts/admin.py                                               |       47 |        0 |    100% |           |
| accounts/forms.py                                               |       50 |        0 |    100% |           |
| accounts/models.py                                              |       32 |        0 |    100% |           |
| accounts/tests.py                                               |      109 |        0 |    100% |           |
| accounts/urls.py                                                |        4 |        0 |    100% |           |
| accounts/views.py                                               |       60 |        1 |     98% |        99 |
| api/\_\_init\_\_.py                                             |        0 |        0 |    100% |           |
| api/api.py                                                      |       11 |        0 |    100% |           |
| api/filters.py                                                  |       67 |        0 |    100% |           |
| api/serializers.py                                              |      120 |        5 |     96% |225-228, 230 |
| api/tests.py                                                    |        9 |        0 |    100% |           |
| api/views.py                                                    |       97 |        1 |     99% |       146 |
| buses/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| buses/asgi.py                                                   |        4 |        0 |    100% |           |
| buses/context\_processors.py                                    |        5 |        0 |    100% |           |
| buses/jinja2.py                                                 |       36 |        1 |     97% |        40 |
| buses/settings.py                                               |      119 |       31 |     74% |99-109, 129, 143-151, 217, 236-244, 261-277, 333 |
| buses/tests.py                                                  |       12 |        0 |    100% |           |
| buses/urls.py                                                   |        5 |        0 |    100% |           |
| buses/utils.py                                                  |       23 |        4 |     83% |     35-38 |
| buses/wsgi.py                                                   |        4 |        0 |    100% |           |
| busstops/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| busstops/admin.py                                               |      324 |       14 |     96% |105-111, 185, 244-252, 334-336, 382, 457, 461, 511, 596, 624 |
| busstops/fields.py                                              |       27 |        0 |    100% |           |
| busstops/forms.py                                               |       46 |        0 |    100% |           |
| busstops/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| busstops/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| busstops/management/commands/import\_noc.py                     |      131 |        4 |     97% |156, 177, 184, 246 |
| busstops/management/commands/import\_tfl.py                     |       66 |       66 |      0% |     1-126 |
| busstops/management/commands/jersey\_routes.py                  |       14 |        0 |    100% |           |
| busstops/management/commands/jersey\_stops.py                   |       12 |        0 |    100% |           |
| busstops/management/commands/lothian\_colours.py                |       17 |        1 |     94% |        19 |
| busstops/management/commands/naptan\_new.py                     |      159 |        5 |     97% |41, 43, 175, 223, 272 |
| busstops/management/commands/nptg\_new.py                       |       96 |        9 |     91% |145, 156, 161, 166-167, 173-174, 176-177 |
| busstops/management/commands/osm\_iom\_stops.py                 |       34 |       34 |      0% |      1-63 |
| busstops/management/commands/update\_search\_indexes.py         |       11 |        0 |    100% |           |
| busstops/management/commands/update\_slugs.py                   |       20 |       20 |      0% |      1-29 |
| busstops/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| busstops/management/tests/test\_import\_ie.py                   |       63 |        0 |    100% |           |
| busstops/management/tests/test\_import\_naptan.py               |       68 |        0 |    100% |           |
| busstops/management/tests/test\_import\_nptg.py                 |       31 |        0 |    100% |           |
| busstops/management/tests/test\_import\_operators.py            |       70 |        0 |    100% |           |
| busstops/middleware.py                                          |       31 |        0 |    100% |           |
| busstops/models.py                                              |      629 |       22 |     97% |273, 298, 324, 448, 485, 535, 619, 622, 656, 694, 844, 877, 956, 968-972, 1057, 1066, 1106, 1121, 1158 |
| busstops/popular\_pages.py                                      |       12 |        0 |    100% |           |
| busstops/tasks.py                                               |       11 |        0 |    100% |           |
| busstops/templatetags/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| busstops/templatetags/date\_range.py                            |       25 |        3 |     88% | 9, 22, 28 |
| busstops/templatetags/test\_urlise.py                           |        8 |        0 |    100% |           |
| busstops/templatetags/urlise.py                                 |       18 |        0 |    100% |           |
| busstops/test\_admin.py                                         |       66 |        0 |    100% |           |
| busstops/test\_middleware.py                                    |       25 |        0 |    100% |           |
| busstops/test\_models.py                                        |      137 |        0 |    100% |           |
| busstops/test\_popular\_pages.py                                |       21 |        0 |    100% |           |
| busstops/test\_views.py                                         |      295 |        0 |    100% |           |
| busstops/urls.py                                                |       20 |        2 |     90% |   135-137 |
| busstops/utils.py                                               |       11 |        0 |    100% |           |
| busstops/views.py                                               |      669 |       48 |     93% |102, 148, 569, 595, 633, 778, 796, 857-860, 862, 976, 996-1001, 1014, 1092, 1120-1121, 1126-1127, 1135-1144, 1206, 1303, 1319-1326, 1333, 1335, 1414, 1471, 1509-1510, 1513-1517, 1667, 1679-1680, 1685, 1697-1698 |
| bustimes/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| bustimes/admin.py                                               |      142 |       14 |     90% |92, 95-96, 107-109, 112-114, 171-175, 198, 219, 222 |
| bustimes/download\_utils.py                                     |       32 |        0 |    100% |           |
| bustimes/fields.py                                              |       31 |        1 |     97% |        12 |
| bustimes/formatting.py                                          |       23 |        0 |    100% |           |
| bustimes/gtfs\_utils.py                                         |       63 |        1 |     98% |        89 |
| bustimes/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| bustimes/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| bustimes/management/commands/bank\_holidays.py                  |       52 |        1 |     98% |       102 |
| bustimes/management/commands/import\_atco\_cif.py               |      235 |       25 |     89% |28-35, 40, 43-44, 71, 204, 206, 209, 211, 219, 225, 289, 322-327, 367-368, 435 |
| bustimes/management/commands/import\_bod\_timetables.py         |      268 |       28 |     90% |35-43, 63, 106, 110, 113-116, 121, 126-127, 151, 179, 189, 200-201, 268, 285-289, 312, 328-329, 345 |
| bustimes/management/commands/import\_gtfs.py                    |      192 |        6 |     97% |66, 119-120, 132, 139, 337 |
| bustimes/management/commands/import\_gtfs\_ember.py             |      154 |        5 |     97% |43, 106, 226, 258, 271 |
| bustimes/management/commands/import\_gtfs\_flixbus.py           |      138 |        3 |     98% |43, 108, 190 |
| bustimes/management/commands/import\_ni.py                      |       31 |        0 |    100% |           |
| bustimes/management/commands/import\_passenger.py               |      116 |       35 |     70% |51-54, 56-58, 64, 103, 113-117, 143-180 |
| bustimes/management/commands/import\_tnds.py                    |       42 |        0 |    100% |           |
| bustimes/management/commands/import\_transxchange.py            |      830 |       93 |     89% |89, 104, 150-151, 234-235, 242, 246, 272-276, 325-326, 336, 344-345, 400, 404, 406, 507, 569-583, 603, 607, 610, 722, 764-765, 802-803, 805-806, 850, 861, 884, 890, 914, 940, 944-946, 995, 1002-1006, 1011-1031, 1059, 1068, 1076-1081, 1097, 1121, 1129, 1131-1134, 1139, 1155, 1185, 1224, 1264-1265, 1292-1294, 1301, 1306-1307, 1322, 1327, 1346, 1371, 1397-1398, 1435-1436, 1498-1499 |
| bustimes/management/commands/suggest\_bod.py                    |       36 |       36 |      0% |      1-51 |
| bustimes/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| bustimes/management/tests/test\_bank\_holidays.py               |       20 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_atco\_cif.py            |       70 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_bod.py                  |      244 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs.py                 |      103 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs\_ember\_flixbus.py |       80 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_ni.py                   |       21 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_passenger.py            |       23 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_transxchange.py         |      784 |        0 |    100% |           |
| bustimes/management/tests/test\_tnds.py                         |       19 |        0 |    100% |           |
| bustimes/models.py                                              |      343 |        6 |     98% |117, 424, 469-472, 504 |
| bustimes/test\_get\_trip.py                                     |       31 |        0 |    100% |           |
| bustimes/tests.py                                               |      132 |        0 |    100% |           |
| bustimes/timetables.py                                          |      646 |       50 |     92% |39-52, 162-173, 204-205, 293, 307-312, 325, 344, 419, 422, 438-441, 443, 470, 582-597, 748-749, 820, 966-968, 1017 |
| bustimes/urls.py                                                |        3 |        0 |    100% |           |
| bustimes/utils.py                                               |      210 |       13 |     94% |175, 244, 275, 284-286, 307-308, 375, 393, 410-411, 485 |
| bustimes/views.py                                               |      453 |      111 |     75% |138-241, 314-315, 318-319, 335-337, 345-354, 356-364, 371, 393, 482, 491, 527, 533, 724, 748-750, 767, 771-799, 827-838, 847-853, 895 |
| departures/\_\_init\_\_.py                                      |        0 |        0 |    100% |           |
| departures/avl.py                                               |       12 |        1 |     92% |        14 |
| departures/gtfsr.py                                             |       91 |        4 |     96% |91, 111, 117-120 |
| departures/live.py                                              |      129 |       18 |     86% |42, 57, 59, 61, 72-83, 144, 155, 167, 181 |
| departures/sources.py                                           |      195 |       35 |     82% |31, 55, 60, 64, 68, 72, 93, 105, 108-110, 120-127, 132-133, 147-148, 156-157, 252, 269-271, 344, 348-349, 355-356, 359 |
| departures/test\_gtfsr\_trip\_updates.py                        |       50 |        0 |    100% |           |
| departures/test\_gtfsr\_vehicle\_positions.py                   |       33 |        0 |    100% |           |
| departures/test\_live.py                                        |       96 |        0 |    100% |           |
| departures/test\_scheduled\_departures.py                       |       18 |        0 |    100% |           |
| disruptions/\_\_init\_\_.py                                     |        0 |        0 |    100% |           |
| disruptions/admin.py                                            |       33 |        1 |     97% |        69 |
| disruptions/models.py                                           |       86 |        6 |     93% |48, 77, 101, 109, 119, 147 |
| disruptions/siri\_sx.py                                         |      124 |       14 |     89% |54, 74, 86-89, 100-101, 132, 142-146 |
| disruptions/tasks.py                                            |        5 |        0 |    100% |           |
| disruptions/test\_siri\_sx.py                                   |       48 |        0 |    100% |           |
| disruptions/test\_tfl\_disruptions.py                           |       34 |        0 |    100% |           |
| disruptions/test\_translinkni.py                                |       25 |        0 |    100% |           |
| disruptions/tests.py                                            |       16 |        0 |    100% |           |
| disruptions/tfl\_disruptions.py                                 |       91 |        2 |     98% |    49, 85 |
| disruptions/translinkni.py                                      |       80 |        7 |     91% |45, 56-59, 68, 112 |
| disruptions/urls.py                                             |        3 |        0 |    100% |           |
| disruptions/views.py                                            |       23 |        0 |    100% |           |
| fares/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| fares/admin.py                                                  |       38 |        1 |     97% |        32 |
| fares/forms.py                                                  |       26 |        3 |     88% | 18, 41-42 |
| fares/management/commands/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| fares/management/commands/import\_netex\_fares.py               |      354 |       59 |     83% |29, 70-71, 122, 129-131, 224-225, 324, 368-369, 450, 529-536, 556, 565-566, 582-587, 594-631, 651-652, 662-663, 669-678 |
| fares/management/commands/mytrip\_ticketing.py                  |       34 |        0 |    100% |           |
| fares/models.py                                                 |      190 |        8 |     96% |60, 142, 217, 222, 245-246, 250-251 |
| fares/mytrip.py                                                 |       53 |        2 |     96% |     49-50 |
| fares/test\_mytrip.py                                           |       47 |        0 |    100% |           |
| fares/tests.py                                                  |       79 |        0 |    100% |           |
| fares/urls.py                                                   |        3 |        0 |    100% |           |
| fares/views.py                                                  |       45 |        0 |    100% |           |
| manage.py                                                       |        6 |        0 |    100% |           |
| photos/\_\_init\_\_.py                                          |        0 |        0 |    100% |           |
| photos/admin.py                                                 |        5 |        0 |    100% |           |
| photos/forms.py                                                 |        3 |        0 |    100% |           |
| photos/models.py                                                |       19 |        1 |     95% |        38 |
| photos/utils.py                                                 |       25 |       18 |     28% |10-12, 16-43 |
| transxchange/\_\_init\_\_.py                                    |        0 |        0 |    100% |           |
| transxchange/test\_txc.py                                       |       23 |        0 |    100% |           |
| transxchange/txc.py                                             |      485 |       19 |     96% |54, 125, 131, 176, 236, 264, 310-317, 384, 386, 430, 451, 513, 546-547, 702, 733 |
| vehicles/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| vehicles/admin.py                                               |      262 |       26 |     90% |34, 62, 89, 91, 203, 208-209, 227-228, 237, 264-265, 268-269, 292, 298, 300, 302, 305, 334, 350, 356, 460, 520-522 |
| vehicles/apps.py                                                |        6 |        0 |    100% |           |
| vehicles/context\_processors.py                                 |       14 |        0 |    100% |           |
| vehicles/fields.py                                              |       23 |        0 |    100% |           |
| vehicles/filters.py                                             |       20 |        0 |    100% |           |
| vehicles/form\_fields.py                                        |       15 |        0 |    100% |           |
| vehicles/forms.py                                               |       94 |        3 |     97% |129, 167, 205 |
| vehicles/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| vehicles/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| vehicles/management/commands/compute\_blocks.py                 |       27 |       27 |      0% |      1-45 |
| vehicles/management/commands/import\_bod\_avl.py                |      400 |       56 |     86% |125, 141, 151-152, 172, 199-202, 205-208, 251, 267, 282-283, 305-323, 374, 376, 382, 403-404, 411, 417, 433, 475-488, 513-514, 520, 527-528, 543, 603, 693, 710 |
| vehicles/management/commands/import\_bushub.py                  |       84 |       18 |     79% |24-25, 29-30, 33-34, 38, 42, 50, 67, 82-83, 91, 101, 120, 128, 135, 153 |
| vehicles/management/commands/import\_first.py                   |      124 |       21 |     83% |28, 32, 52, 54, 75-76, 82, 104-105, 114, 136-148, 153, 212-213, 215 |
| vehicles/management/commands/import\_gtfsr\_ember.py            |       50 |        0 |    100% |           |
| vehicles/management/commands/import\_gtfsr\_ie.py               |       86 |        4 |     95% |94, 105, 135, 142 |
| vehicles/management/commands/import\_live\_jersey.py            |       39 |        0 |    100% |           |
| vehicles/management/commands/import\_stagecoach\_avl.py         |       72 |        7 |     90% |119, 129, 134-136, 168-169 |
| vehicles/management/commands/import\_translink\_avl.py          |       57 |        7 |     88% |14, 67-70, 104-105 |
| vehicles/management/commands/listen.py                          |       24 |        0 |    100% |           |
| vehicles/management/commands/lothian.py                         |       56 |        0 |    100% |           |
| vehicles/management/commands/newport.py                         |       44 |        2 |     95% |    46, 64 |
| vehicles/management/commands/signalr.py                         |       82 |        0 |    100% |           |
| vehicles/management/commands/siri\_vm\_subscribe.py             |       43 |        2 |     95% |    41, 49 |
| vehicles/management/import\_live\_vehicles.py                   |      310 |       34 |     89% |86, 99-117, 129, 135, 141-143, 145, 173, 182, 196, 205-208, 238, 243, 252, 257, 314-315, 356, 359-360, 381-382, 484, 522-523, 533, 553 |
| vehicles/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| vehicles/management/tests/test\_bod\_avl.py                     |      323 |        0 |    100% |           |
| vehicles/management/tests/test\_bushub.py                       |       48 |        0 |    100% |           |
| vehicles/management/tests/test\_edinburgh.py                    |       46 |        0 |    100% |           |
| vehicles/management/tests/test\_first.py                        |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_live\_jersey.py         |       46 |        0 |    100% |           |
| vehicles/management/tests/test\_listen.py                       |       15 |        0 |    100% |           |
| vehicles/management/tests/test\_newport.py                      |       23 |        0 |    100% |           |
| vehicles/management/tests/test\_signalr.py                      |       28 |        0 |    100% |           |
| vehicles/management/tests/test\_siri\_post.py                   |       50 |        0 |    100% |           |
| vehicles/management/tests/test\_stagecoach\_avl.py              |       34 |        0 |    100% |           |
| vehicles/management/tests/test\_stats.py                        |       24 |        0 |    100% |           |
| vehicles/management/tests/test\_translink\_avl.py               |       22 |        0 |    100% |           |
| vehicles/models.py                                              |      517 |       35 |     93% |75, 193, 218, 285, 304, 310, 382, 388, 439, 460, 581-582, 595, 603, 620-622, 630-631, 634-635, 637-642, 647-648, 679, 760-763, 818, 827, 853 |
| vehicles/rtpi.py                                                |       93 |        6 |     94% |37, 81-82, 88-90 |
| vehicles/signals.py                                             |       11 |        0 |    100% |           |
| vehicles/tasks.py                                               |      163 |       36 |     78% |96, 101, 113, 120-123, 126, 143, 156, 160-161, 183, 208, 216-217, 225, 288-289, 292, 313-333 |
| vehicles/test\_models.py                                        |       62 |        0 |    100% |           |
| vehicles/test\_schedule\_adherence.py                           |       75 |        0 |    100% |           |
| vehicles/tests.py                                               |      461 |        0 |    100% |           |
| vehicles/time\_aware\_polyline.py                               |       56 |       28 |     50% |18, 36, 49, 54, 57, 87-98, 106-120 |
| vehicles/urls.py                                                |        4 |        0 |    100% |           |
| vehicles/utils.py                                               |      128 |        6 |     95% |29, 59, 162, 174-175, 179 |
| vehicles/views.py                                               |      645 |       64 |     90% |460-461, 480-481, 494, 512-513, 565, 581-582, 587, 603-604, 641-642, 656-658, 667, 675, 697-702, 736, 750, 758-761, 767-775, 787, 894, 896, 898, 903, 953-954, 966-968, 1055, 1058-1059, 1069, 1137-1139, 1158-1159, 1177-1187, 1191, 1193, 1217 |
| vosa/\_\_init\_\_.py                                            |        0 |        0 |    100% |           |
| vosa/admin.py                                                   |       37 |        0 |    100% |           |
| vosa/management/commands/\_\_init\_\_.py                        |        0 |        0 |    100% |           |
| vosa/management/commands/import\_vosa.py                        |      162 |        3 |     98% |25-26, 206 |
| vosa/models.py                                                  |       75 |        0 |    100% |           |
| vosa/tests.py                                                   |       60 |        0 |    100% |           |
| vosa/urls.py                                                    |        3 |        0 |    100% |           |
| vosa/views.py                                                   |       59 |        0 |    100% |           |
| **TOTAL**                                                       | **17410** | **1283** | **93%** |           |


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