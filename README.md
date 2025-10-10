# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| accounts/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| accounts/admin.py                                               |       47 |        0 |    100% |           |
| accounts/forms.py                                               |       57 |        0 |    100% |           |
| accounts/models.py                                              |       32 |        0 |    100% |           |
| accounts/tests.py                                               |      114 |        0 |    100% |           |
| accounts/urls.py                                                |        4 |        0 |    100% |           |
| accounts/views.py                                               |       60 |        1 |     98% |        99 |
| api/\_\_init\_\_.py                                             |        0 |        0 |    100% |           |
| api/api.py                                                      |       11 |        0 |    100% |           |
| api/filters.py                                                  |       67 |        0 |    100% |           |
| api/serializers.py                                              |      111 |        4 |     96% |   221-224 |
| api/tests.py                                                    |        9 |        0 |    100% |           |
| api/views.py                                                    |       94 |        0 |    100% |           |
| buses/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| buses/asgi.py                                                   |        4 |        4 |      0% |     10-16 |
| buses/context\_processors.py                                    |        5 |        0 |    100% |           |
| buses/jinja2.py                                                 |       36 |        1 |     97% |        40 |
| buses/settings.py                                               |      121 |       31 |     74% |97-107, 127, 144-152, 208, 227-235, 252-268, 320 |
| buses/tests.py                                                  |        5 |        0 |    100% |           |
| buses/urls.py                                                   |        5 |        0 |    100% |           |
| buses/utils.py                                                  |       23 |        4 |     83% |     35-38 |
| buses/wsgi.py                                                   |        4 |        4 |      0% |     10-16 |
| busstops/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| busstops/admin.py                                               |      321 |       14 |     96% |104-110, 185, 244-252, 334-336, 382, 457, 461, 510, 593, 621 |
| busstops/fields.py                                              |        6 |        0 |    100% |           |
| busstops/forms.py                                               |       46 |        0 |    100% |           |
| busstops/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| busstops/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| busstops/management/commands/import\_noc.py                     |      125 |        3 |     98% |155, 179, 238 |
| busstops/management/commands/naptan\_new.py                     |      158 |       11 |     93% |41, 43, 167-176, 219, 268 |
| busstops/management/commands/nptg\_new.py                       |       94 |        7 |     93% |148, 158, 163, 169-170, 172-173 |
| busstops/management/commands/osm\_iom\_stops.py                 |       34 |       34 |      0% |      1-63 |
| busstops/management/commands/update\_search\_indexes.py         |       11 |        0 |    100% |           |
| busstops/management/commands/update\_slugs.py                   |       20 |       20 |      0% |      1-29 |
| busstops/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| busstops/management/tests/test\_import\_ie.py                   |       63 |        0 |    100% |           |
| busstops/management/tests/test\_import\_naptan.py               |       67 |        0 |    100% |           |
| busstops/management/tests/test\_import\_nptg.py                 |       31 |        0 |    100% |           |
| busstops/management/tests/test\_import\_operators.py            |       64 |        0 |    100% |           |
| busstops/middleware.py                                          |       37 |        0 |    100% |           |
| busstops/models.py                                              |      620 |       22 |     96% |271, 296, 322, 440, 477, 527, 553, 609, 643, 681, 833, 866, 937, 949-953, 1038, 1047, 1087, 1102, 1139 |
| busstops/templatetags/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| busstops/templatetags/date\_range.py                            |       25 |        3 |     88% | 9, 22, 28 |
| busstops/templatetags/urlise.py                                 |       16 |        0 |    100% |           |
| busstops/test\_admin.py                                         |       66 |        0 |    100% |           |
| busstops/test\_middleware.py                                    |       25 |        0 |    100% |           |
| busstops/test\_models.py                                        |      137 |        0 |    100% |           |
| busstops/test\_views.py                                         |      280 |        0 |    100% |           |
| busstops/urls.py                                                |       20 |        2 |     90% |   134-136 |
| busstops/utils.py                                               |       11 |        0 |    100% |           |
| busstops/views.py                                               |      648 |       43 |     93% |140, 481, 507, 545, 690, 708, 768-771, 773, 904-909, 922, 999, 1027-1028, 1033-1034, 1042-1051, 1112, 1208, 1229, 1231, 1310, 1389, 1419-1420, 1423-1427, 1577, 1589-1590, 1595, 1607-1608 |
| bustimes/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| bustimes/admin.py                                               |      136 |       14 |     90% |74, 77-78, 89-91, 94-96, 153-157, 180, 201, 204 |
| bustimes/download\_utils.py                                     |       32 |        0 |    100% |           |
| bustimes/fields.py                                              |       31 |        1 |     97% |        12 |
| bustimes/formatting.py                                          |       19 |        0 |    100% |           |
| bustimes/gtfs\_utils.py                                         |       15 |        0 |    100% |           |
| bustimes/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| bustimes/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| bustimes/management/commands/bank\_holidays.py                  |       52 |        1 |     98% |       102 |
| bustimes/management/commands/import\_atco\_cif.py               |      235 |       25 |     89% |28-35, 40, 43-44, 71, 203, 205, 208, 210, 218, 224, 288, 321-326, 366-367, 434 |
| bustimes/management/commands/import\_bod\_timetables.py         |      271 |       25 |     91% |48, 99, 103, 106-109, 114, 119-120, 141, 169, 179, 191-192, 259, 269-273, 289-291, 314, 330-331, 347 |
| bustimes/management/commands/import\_gtfs.py                    |      227 |        6 |     97% |69, 122-123, 135, 142, 339 |
| bustimes/management/commands/import\_gtfs\_ember.py             |      149 |        9 |     94% |82, 87, 105, 130, 171, 182, 192, 269-270 |
| bustimes/management/commands/import\_gtfs\_flixbus.py           |      170 |        8 |     95% |45, 110, 180, 279-280, 304-305, 319 |
| bustimes/management/commands/import\_ni.py                      |       31 |        0 |    100% |           |
| bustimes/management/commands/import\_passenger.py               |      116 |       35 |     70% |51-54, 56-58, 64, 103, 113-117, 143-180 |
| bustimes/management/commands/import\_tnds.py                    |       43 |        0 |    100% |           |
| bustimes/management/commands/import\_transxchange.py            |      799 |       85 |     89% |85, 100, 146-147, 229-230, 237, 241, 267-271, 320-321, 331, 339-340, 395, 399, 401, 501, 563-577, 597, 600, 712, 754-755, 792-793, 795-796, 840, 851, 873, 895, 921, 925-927, 939-940, 983-987, 1028, 1038-1043, 1057, 1081, 1089, 1091-1094, 1115, 1142, 1181, 1212-1213, 1240-1242, 1249, 1254-1255, 1271, 1276, 1289, 1314, 1340-1341, 1377-1378, 1429 |
| bustimes/management/commands/poo.py                             |       33 |       33 |      0% |      1-63 |
| bustimes/management/commands/suggest\_bod.py                    |       36 |       36 |      0% |      1-51 |
| bustimes/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| bustimes/management/tests/test\_bank\_holidays.py               |       20 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_atco\_cif.py            |       70 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_bod.py                  |      242 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs.py                 |      103 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs\_ember\_flixbus.py |       79 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_ni.py                   |       21 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_passenger.py            |       23 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_transxchange.py         |      754 |        0 |    100% |           |
| bustimes/management/tests/test\_tnds.py                         |       19 |        0 |    100% |           |
| bustimes/models.py                                              |      342 |        8 |     98% |111, 375, 378, 407, 452-455, 487 |
| bustimes/test\_get\_trip.py                                     |       31 |        0 |    100% |           |
| bustimes/tests.py                                               |      129 |        0 |    100% |           |
| bustimes/timetables.py                                          |      615 |       64 |     90% |39-52, 162-173, 204-205, 222-234, 286, 298-301, 313, 327-332, 346, 365, 440, 443, 459-462, 464, 491, 603-618, 704-705, 776, 922-924 |
| bustimes/urls.py                                                |        3 |        0 |    100% |           |
| bustimes/utils.py                                               |      180 |       11 |     94% |156, 211, 237-239, 259-260, 329, 346-347, 395 |
| bustimes/views.py                                               |      383 |       66 |     83% |195-196, 199-200, 216-218, 226-235, 237-245, 252, 274, 364, 373, 409, 415, 495, 585, 609-611, 628, 632-660, 688-699, 708-714 |
| departures/\_\_init\_\_.py                                      |        0 |        0 |    100% |           |
| departures/avl.py                                               |       12 |        1 |     92% |        14 |
| departures/gtfsr.py                                             |       91 |        2 |     98% |   91, 111 |
| departures/live.py                                              |      134 |       14 |     90% |44, 59, 61, 63, 80-85, 146, 157, 169, 183 |
| departures/sources.py                                           |      224 |       34 |     85% |34, 58, 63, 67, 100, 116, 126, 129-131, 141-148, 153-154, 168-169, 177-178, 245, 324, 341, 414, 418-419, 425-426, 429, 437 |
| departures/test\_gtfsr\_trip\_updates.py                        |       45 |        0 |    100% |           |
| departures/test\_gtfsr\_vehicle\_positions.py                   |       33 |        0 |    100% |           |
| departures/test\_live.py                                        |      111 |        0 |    100% |           |
| disruptions/\_\_init\_\_.py                                     |        0 |        0 |    100% |           |
| disruptions/admin.py                                            |       33 |        1 |     97% |        69 |
| disruptions/models.py                                           |       86 |        6 |     93% |47, 76, 100, 108, 118, 146 |
| disruptions/siri\_sx.py                                         |      124 |       14 |     89% |54, 74, 86-89, 100-101, 132, 142-146 |
| disruptions/tasks.py                                            |        5 |        5 |      0% |       1-7 |
| disruptions/test\_siri\_sx.py                                   |       48 |        0 |    100% |           |
| disruptions/test\_tfl\_disruptions.py                           |       34 |        0 |    100% |           |
| disruptions/tests.py                                            |       16 |        0 |    100% |           |
| disruptions/tfl\_disruptions.py                                 |       91 |        2 |     98% |    49, 85 |
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
| vehicles/admin.py                                               |      254 |       24 |     91% |32, 60, 87, 89, 205, 223-224, 233, 260-261, 264-265, 288, 294, 296, 298, 301, 330, 346, 352, 456, 516-518 |
| vehicles/apps.py                                                |        6 |        0 |    100% |           |
| vehicles/context\_processors.py                                 |       14 |        0 |    100% |           |
| vehicles/fields.py                                              |       23 |        0 |    100% |           |
| vehicles/filters.py                                             |       20 |        0 |    100% |           |
| vehicles/form\_fields.py                                        |       15 |        0 |    100% |           |
| vehicles/forms.py                                               |       94 |        3 |     97% |129, 167, 205 |
| vehicles/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| vehicles/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| vehicles/management/commands/compute\_blocks.py                 |       27 |       27 |      0% |      1-47 |
| vehicles/management/commands/import\_bod\_avl.py                |      400 |       55 |     86% |51, 126, 142, 152-153, 196-199, 202-205, 248, 264, 279-280, 302-320, 371, 373, 379, 410, 416, 431-432, 473-486, 514, 521-522, 537, 566, 600, 696, 708, 712 |
| vehicles/management/commands/import\_bushub.py                  |       87 |       18 |     79% |23-24, 28-29, 32-33, 37, 41, 49, 60, 63, 79-80, 89, 99, 118, 126, 152 |
| vehicles/management/commands/import\_edinburgh.py               |       63 |        4 |     94% |44, 72, 78-79 |
| vehicles/management/commands/import\_first.py                   |      122 |       21 |     83% |28, 32, 52, 54, 75-76, 82, 98-99, 108, 130-142, 147, 206-207, 209 |
| vehicles/management/commands/import\_gtfsr\_ember.py            |       44 |        1 |     98% |        53 |
| vehicles/management/commands/import\_gtfsr\_ie.py               |       96 |        4 |     96% |94, 140, 149, 156 |
| vehicles/management/commands/import\_live\_jersey.py            |       44 |        3 |     93% |27, 31, 39 |
| vehicles/management/commands/import\_polar.py                   |       84 |       28 |     67% |13-14, 25, 29, 33, 41, 44, 49-55, 61-63, 67, 77-78, 81, 95-98, 101, 114, 121 |
| vehicles/management/commands/import\_stagecoach\_avl.py         |       72 |        5 |     93% |123, 133, 138-139, 171 |
| vehicles/management/commands/import\_translink\_avl.py          |       58 |        7 |     88% |14, 68-71, 105-106 |
| vehicles/management/commands/listen.py                          |       22 |        0 |    100% |           |
| vehicles/management/commands/newport.py                         |       43 |        2 |     95% |    45, 61 |
| vehicles/management/commands/signalr.py                         |       79 |        0 |    100% |           |
| vehicles/management/commands/siri\_vm\_subscribe.py             |       27 |        7 |     74% |     29-58 |
| vehicles/management/import\_live\_vehicles.py                   |      305 |       32 |     90% |112, 128, 134-136, 138, 160, 169, 183, 192-195, 204, 225, 230, 237-240, 247, 310-311, 352, 355-356, 377-378, 480, 518-519, 529, 549 |
| vehicles/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| vehicles/management/tests/test\_bod\_avl.py                     |      293 |        0 |    100% |           |
| vehicles/management/tests/test\_bushub.py                       |       48 |        0 |    100% |           |
| vehicles/management/tests/test\_edinburgh.py                    |       49 |        0 |    100% |           |
| vehicles/management/tests/test\_first.py                        |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_live\_jersey.py         |       31 |        0 |    100% |           |
| vehicles/management/tests/test\_listen.py                       |       15 |        0 |    100% |           |
| vehicles/management/tests/test\_newport.py                      |       23 |        0 |    100% |           |
| vehicles/management/tests/test\_polar.py                        |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_signalr.py                      |       28 |        0 |    100% |           |
| vehicles/management/tests/test\_siri\_post.py                   |       51 |        0 |    100% |           |
| vehicles/management/tests/test\_stagecoach\_avl.py              |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_stats.py                        |       24 |        0 |    100% |           |
| vehicles/management/tests/test\_translink\_avl.py               |       22 |        0 |    100% |           |
| vehicles/models.py                                              |      502 |       35 |     93% |75, 193, 218, 285, 304, 310, 382, 388, 439, 460, 575-576, 589, 597, 614-616, 624-625, 628-629, 634-635, 660, 681-685, 723-726, 781, 790, 806 |
| vehicles/rtpi.py                                                |       76 |        1 |     99% |        28 |
| vehicles/signals.py                                             |       11 |        0 |    100% |           |
| vehicles/tasks.py                                               |      136 |       22 |     84% |80, 85, 95, 102-105, 108, 110, 119, 132, 136-137, 155, 169, 182, 188-189, 197, 249-250, 253 |
| vehicles/test\_models.py                                        |       62 |        0 |    100% |           |
| vehicles/test\_schedule\_adherence.py                           |       75 |        0 |    100% |           |
| vehicles/tests.py                                               |      449 |        0 |    100% |           |
| vehicles/time\_aware\_polyline.py                               |       56 |       28 |     50% |18, 36, 49, 54, 57, 87-98, 106-120 |
| vehicles/urls.py                                                |        4 |        0 |    100% |           |
| vehicles/utils.py                                               |      116 |        5 |     96% |41, 144, 156-157, 161 |
| vehicles/views.py                                               |      604 |       53 |     91% |351-352, 392, 419, 443-444, 463-464, 477, 495-496, 548, 566-567, 572, 588-589, 607-626, 704-705, 717, 825, 827, 829, 834, 879-880, 892-894, 981, 984-985, 995, 1011-1016, 1063-1065, 1084-1085, 1103-1113, 1117, 1119 |
| vosa/\_\_init\_\_.py                                            |        0 |        0 |    100% |           |
| vosa/admin.py                                                   |       36 |        0 |    100% |           |
| vosa/management/commands/\_\_init\_\_.py                        |        0 |        0 |    100% |           |
| vosa/management/commands/import\_vosa.py                        |      162 |        3 |     98% |25-26, 206 |
| vosa/models.py                                                  |       75 |        0 |    100% |           |
| vosa/tests.py                                                   |       60 |        0 |    100% |           |
| vosa/urls.py                                                    |        3 |        0 |    100% |           |
| vosa/views.py                                                   |       57 |        0 |    100% |           |
|                                                       **TOTAL** | **16788** | **1194** | **93%** |           |


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