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
| api/serializers.py                                              |      114 |        4 |     96% |   222-225 |
| api/tests.py                                                    |        9 |        0 |    100% |           |
| api/views.py                                                    |       92 |        0 |    100% |           |
| buses/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| buses/asgi.py                                                   |        4 |        0 |    100% |           |
| buses/context\_processors.py                                    |        5 |        0 |    100% |           |
| buses/jinja2.py                                                 |       36 |        1 |     97% |        40 |
| buses/settings.py                                               |      120 |       31 |     74% |104-114, 134, 148-156, 212, 231-239, 256-272, 324 |
| buses/tests.py                                                  |       12 |        0 |    100% |           |
| buses/urls.py                                                   |        5 |        0 |    100% |           |
| buses/utils.py                                                  |       23 |        4 |     83% |     35-38 |
| buses/wsgi.py                                                   |        4 |        0 |    100% |           |
| busstops/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| busstops/admin.py                                               |      321 |       14 |     96% |104-110, 186, 245-253, 335-337, 383, 458, 462, 511, 594, 622 |
| busstops/fields.py                                              |       27 |        1 |     96% |        42 |
| busstops/forms.py                                               |       46 |        0 |    100% |           |
| busstops/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| busstops/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| busstops/management/commands/import\_noc.py                     |      126 |        3 |     98% |155, 179, 240 |
| busstops/management/commands/jersey\_routes.py                  |       14 |        0 |    100% |           |
| busstops/management/commands/jersey\_stops.py                   |       12 |        0 |    100% |           |
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
| busstops/models.py                                              |      622 |       22 |     96% |271, 296, 322, 440, 477, 527, 553, 609, 643, 681, 833, 866, 945, 957-961, 1046, 1055, 1095, 1110, 1147 |
| busstops/templatetags/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| busstops/templatetags/date\_range.py                            |       25 |        3 |     88% | 9, 22, 28 |
| busstops/templatetags/urlise.py                                 |       18 |        0 |    100% |           |
| busstops/test\_admin.py                                         |       66 |        0 |    100% |           |
| busstops/test\_middleware.py                                    |       25 |        0 |    100% |           |
| busstops/test\_models.py                                        |      137 |        0 |    100% |           |
| busstops/test\_views.py                                         |      277 |        0 |    100% |           |
| busstops/urls.py                                                |       20 |        2 |     90% |   134-136 |
| busstops/utils.py                                               |       11 |        0 |    100% |           |
| busstops/views.py                                               |      658 |       50 |     92% |101, 146, 489, 515, 553, 611-612, 698, 716, 776-779, 781, 894, 914-919, 932, 1009, 1037-1038, 1043-1044, 1052-1061, 1123, 1219, 1235-1242, 1249, 1251, 1330, 1409, 1439-1440, 1443-1447, 1597, 1609-1610, 1615, 1627-1628 |
| bustimes/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| bustimes/admin.py                                               |      142 |       14 |     90% |92, 95-96, 107-109, 112-114, 171-175, 198, 219, 222 |
| bustimes/download\_utils.py                                     |       32 |        0 |    100% |           |
| bustimes/fields.py                                              |       31 |        1 |     97% |        12 |
| bustimes/formatting.py                                          |       19 |        0 |    100% |           |
| bustimes/gtfs\_utils.py                                         |       15 |        0 |    100% |           |
| bustimes/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| bustimes/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| bustimes/management/commands/bank\_holidays.py                  |       52 |        1 |     98% |       102 |
| bustimes/management/commands/import\_atco\_cif.py               |      235 |       25 |     89% |28-35, 40, 43-44, 71, 204, 206, 209, 211, 219, 225, 289, 322-327, 367-368, 435 |
| bustimes/management/commands/import\_bod\_timetables.py         |      275 |       28 |     90% |36-44, 64, 115, 119, 122-125, 130, 135-136, 160, 188, 198, 209-210, 277, 294-298, 321, 337-338, 354 |
| bustimes/management/commands/import\_gtfs.py                    |      227 |        6 |     97% |69, 122-123, 135, 142, 339 |
| bustimes/management/commands/import\_gtfs\_ember.py             |      149 |        8 |     95% |82, 87, 105, 130, 171, 191, 268-269 |
| bustimes/management/commands/import\_gtfs\_flixbus.py           |      174 |        8 |     95% |45, 110, 188, 291-292, 316-317, 331 |
| bustimes/management/commands/import\_ni.py                      |       31 |        0 |    100% |           |
| bustimes/management/commands/import\_passenger.py               |      116 |       35 |     70% |51-54, 56-58, 64, 103, 113-117, 143-180 |
| bustimes/management/commands/import\_tnds.py                    |       43 |        0 |    100% |           |
| bustimes/management/commands/import\_transxchange.py            |      798 |       85 |     89% |85, 100, 146-147, 229-230, 237, 241, 267-271, 320-321, 331, 339-340, 395, 399, 401, 495, 558-572, 592, 595, 707, 749-750, 787-788, 790-791, 835, 846, 869, 875, 899, 925, 929-931, 943-944, 987-991, 1032, 1042-1047, 1061, 1085, 1093, 1095-1098, 1119, 1146, 1185, 1216-1217, 1244-1246, 1253, 1258-1259, 1275, 1280, 1293, 1318, 1344-1345, 1381-1382 |
| bustimes/management/commands/suggest\_bod.py                    |       36 |       36 |      0% |      1-51 |
| bustimes/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| bustimes/management/tests/test\_bank\_holidays.py               |       20 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_atco\_cif.py            |       70 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_bod.py                  |      244 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs.py                 |      103 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs\_ember\_flixbus.py |       80 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_ni.py                   |       21 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_passenger.py            |       23 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_transxchange.py         |      768 |        0 |    100% |           |
| bustimes/management/tests/test\_tnds.py                         |       19 |        0 |    100% |           |
| bustimes/models.py                                              |      344 |        9 |     97% |114, 220, 378, 381, 427, 472-475, 507 |
| bustimes/test\_get\_trip.py                                     |       31 |        0 |    100% |           |
| bustimes/tests.py                                               |      132 |        0 |    100% |           |
| bustimes/timetables.py                                          |      613 |       64 |     90% |39-52, 162-173, 204-205, 222-234, 286, 298-301, 313, 327-332, 346, 365, 440, 443, 459-462, 464, 491, 603-618, 704-705, 776, 922-924 |
| bustimes/urls.py                                                |        3 |        0 |    100% |           |
| bustimes/utils.py                                               |      195 |       12 |     94% |158, 214, 243, 252-254, 275-276, 352, 369-370, 444 |
| bustimes/views.py                                               |      385 |       65 |     83% |194-195, 198-199, 215-217, 225-234, 236-244, 251, 273, 363, 372, 408, 414, 584, 608-610, 627, 631-659, 687-698, 707-713 |
| departures/\_\_init\_\_.py                                      |        0 |        0 |    100% |           |
| departures/avl.py                                               |       12 |        1 |     92% |        14 |
| departures/gtfsr.py                                             |       91 |        2 |     98% |   91, 111 |
| departures/live.py                                              |      134 |       14 |     90% |44, 59, 61, 63, 80-85, 146, 157, 169, 183 |
| departures/sources.py                                           |      221 |       34 |     85% |33, 57, 62, 66, 99, 115, 125, 128-130, 140-147, 152-153, 167-168, 176-177, 244, 322-323, 338, 411, 415-416, 422-423, 426 |
| departures/test\_gtfsr\_trip\_updates.py                        |       45 |        0 |    100% |           |
| departures/test\_gtfsr\_vehicle\_positions.py                   |       33 |        0 |    100% |           |
| departures/test\_live.py                                        |      111 |        0 |    100% |           |
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
| fares/admin.py                                                  |       37 |        1 |     97% |        31 |
| fares/forms.py                                                  |       26 |        3 |     88% | 18, 41-42 |
| fares/management/commands/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| fares/management/commands/import\_netex\_fares.py               |      353 |       59 |     83% |28, 69-70, 121, 128-130, 223-224, 323, 367-368, 449, 528-535, 555, 564-565, 583-588, 595-632, 652-653, 663-664, 670-679 |
| fares/management/commands/mytrip\_ticketing.py                  |       34 |        0 |    100% |           |
| fares/models.py                                                 |      176 |        8 |     95% |60, 142, 217, 222, 245-246, 250-251 |
| fares/mytrip.py                                                 |       53 |        2 |     96% |     49-50 |
| fares/test\_mytrip.py                                           |       47 |        0 |    100% |           |
| fares/tests.py                                                  |       79 |        0 |    100% |           |
| fares/urls.py                                                   |        3 |        0 |    100% |           |
| fares/views.py                                                  |       44 |        0 |    100% |           |
| manage.py                                                       |        6 |        0 |    100% |           |
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
| vehicles/management/commands/import\_bod\_avl.py                |      405 |       56 |     86% |126, 142, 152-153, 173, 200-203, 206-209, 252, 268, 283-284, 306-324, 375, 377, 383, 414, 420, 436, 478-491, 516-517, 523, 530-531, 546, 575, 609, 705, 717, 721 |
| vehicles/management/commands/import\_bushub.py                  |       84 |       18 |     79% |24-25, 29-30, 33-34, 38, 42, 50, 67, 82-83, 91, 101, 120, 128, 135, 153 |
| vehicles/management/commands/import\_first.py                   |      124 |       21 |     83% |28, 32, 52, 54, 75-76, 82, 104-105, 114, 136-148, 153, 212-213, 215 |
| vehicles/management/commands/import\_gtfsr\_ember.py            |       44 |        1 |     98% |        53 |
| vehicles/management/commands/import\_gtfsr\_ie.py               |       88 |        3 |     97% |94, 138, 145 |
| vehicles/management/commands/import\_live\_jersey.py            |       39 |        0 |    100% |           |
| vehicles/management/commands/import\_polar.py                   |       67 |       12 |     82% |13-14, 37, 52-54, 65, 75-78, 81 |
| vehicles/management/commands/import\_stagecoach\_avl.py         |       72 |        7 |     90% |123, 133, 138-140, 172-173 |
| vehicles/management/commands/import\_translink\_avl.py          |       57 |        7 |     88% |14, 67-70, 104-105 |
| vehicles/management/commands/listen.py                          |       22 |        0 |    100% |           |
| vehicles/management/commands/lothian.py                         |       56 |        0 |    100% |           |
| vehicles/management/commands/newport.py                         |       44 |        2 |     95% |    46, 64 |
| vehicles/management/commands/signalr.py                         |       82 |        0 |    100% |           |
| vehicles/management/commands/siri\_vm\_subscribe.py             |       43 |        2 |     95% |    41, 49 |
| vehicles/management/import\_live\_vehicles.py                   |      309 |       29 |     91% |117, 129, 135, 141-143, 145, 167, 176, 190, 199-202, 232, 237, 246, 251, 308-309, 350, 353-354, 375-376, 478, 516-517, 527, 547 |
| vehicles/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| vehicles/management/tests/test\_bod\_avl.py                     |      303 |        0 |    100% |           |
| vehicles/management/tests/test\_bushub.py                       |       47 |        0 |    100% |           |
| vehicles/management/tests/test\_edinburgh.py                    |       43 |        0 |    100% |           |
| vehicles/management/tests/test\_first.py                        |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_live\_jersey.py         |       46 |        0 |    100% |           |
| vehicles/management/tests/test\_listen.py                       |       15 |        0 |    100% |           |
| vehicles/management/tests/test\_newport.py                      |       23 |        0 |    100% |           |
| vehicles/management/tests/test\_polar.py                        |       31 |        0 |    100% |           |
| vehicles/management/tests/test\_signalr.py                      |       28 |        0 |    100% |           |
| vehicles/management/tests/test\_siri\_post.py                   |       50 |        0 |    100% |           |
| vehicles/management/tests/test\_stagecoach\_avl.py              |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_stats.py                        |       24 |        0 |    100% |           |
| vehicles/management/tests/test\_translink\_avl.py               |       22 |        0 |    100% |           |
| vehicles/models.py                                              |      517 |       35 |     93% |75, 193, 218, 285, 304, 310, 382, 388, 439, 460, 581-582, 595, 603, 620-622, 630-631, 634-635, 637-642, 647-648, 679, 760-763, 818, 827, 853 |
| vehicles/rtpi.py                                                |       76 |        1 |     99% |        28 |
| vehicles/signals.py                                             |       11 |        0 |    100% |           |
| vehicles/tasks.py                                               |      142 |       21 |     85% |86, 91, 101, 108-111, 114, 116, 133, 146, 150-151, 173, 198, 206-207, 215, 267-268, 271 |
| vehicles/test\_models.py                                        |       62 |        0 |    100% |           |
| vehicles/test\_schedule\_adherence.py                           |       75 |        0 |    100% |           |
| vehicles/tests.py                                               |      460 |        0 |    100% |           |
| vehicles/time\_aware\_polyline.py                               |       56 |       28 |     50% |18, 36, 49, 54, 57, 87-98, 106-120 |
| vehicles/urls.py                                                |        4 |        0 |    100% |           |
| vehicles/utils.py                                               |      116 |        5 |     96% |41, 144, 156-157, 161 |
| vehicles/views.py                                               |      617 |       52 |     92% |443-444, 463-464, 477, 495-496, 548, 564-565, 570, 586-587, 624-625, 639-641, 650, 658, 680-685, 739, 846, 848, 850, 855, 905-906, 918-920, 1007, 1010-1011, 1021, 1089-1091, 1110-1111, 1129-1139, 1143, 1145, 1169 |
| vosa/\_\_init\_\_.py                                            |        0 |        0 |    100% |           |
| vosa/admin.py                                                   |       36 |        0 |    100% |           |
| vosa/management/commands/\_\_init\_\_.py                        |        0 |        0 |    100% |           |
| vosa/management/commands/import\_vosa.py                        |      162 |        3 |     98% |25-26, 206 |
| vosa/models.py                                                  |       75 |        0 |    100% |           |
| vosa/tests.py                                                   |       60 |        0 |    100% |           |
| vosa/urls.py                                                    |        3 |        0 |    100% |           |
| vosa/views.py                                                   |       59 |        0 |    100% |           |
| **TOTAL**                                                       | **17025** | **1133** | **93%** |           |


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