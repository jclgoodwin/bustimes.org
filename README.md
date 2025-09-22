# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| accounts/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| accounts/admin.py                                               |       47 |        0 |    100% |           |
| accounts/forms.py                                               |       57 |        0 |    100% |           |
| accounts/models.py                                              |       32 |        0 |    100% |           |
| accounts/tests.py                                               |      104 |        0 |    100% |           |
| accounts/urls.py                                                |        4 |        0 |    100% |           |
| accounts/views.py                                               |       60 |        1 |     98% |        99 |
| api/\_\_init\_\_.py                                             |        0 |        0 |    100% |           |
| api/api.py                                                      |       11 |        0 |    100% |           |
| api/filters.py                                                  |       67 |        6 |     91% |65-69, 106 |
| api/serializers.py                                              |      111 |        4 |     96% |   221-224 |
| api/tests.py                                                    |        9 |        0 |    100% |           |
| api/views.py                                                    |       94 |        0 |    100% |           |
| buses/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| buses/context\_processors.py                                    |        5 |        0 |    100% |           |
| buses/jinja2.py                                                 |       36 |        2 |     94% |    40, 61 |
| buses/settings.py                                               |      121 |       31 |     74% |96-105, 122, 141-149, 205, 224-232, 249-265, 317 |
| buses/tests.py                                                  |        5 |        0 |    100% |           |
| buses/urls.py                                                   |        5 |        0 |    100% |           |
| buses/utils.py                                                  |       23 |        4 |     83% |     34-37 |
| busstops/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| busstops/admin.py                                               |      318 |       16 |     95% |103-109, 184, 243-251, 333-334, 380, 455, 459, 508, 542, 586, 590, 614, 618 |
| busstops/forms.py                                               |       46 |        0 |    100% |           |
| busstops/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| busstops/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| busstops/management/commands/import\_noc.py                     |      125 |        3 |     98% |155, 179, 238 |
| busstops/management/commands/naptan\_new.py                     |      161 |       11 |     93% |39, 41, 165-174, 215, 264 |
| busstops/management/commands/nptg\_new.py                       |       94 |        7 |     93% |148, 158, 163, 169-170, 172-173 |
| busstops/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| busstops/management/tests/test\_import\_ie.py                   |       63 |        0 |    100% |           |
| busstops/management/tests/test\_import\_naptan.py               |       67 |        0 |    100% |           |
| busstops/management/tests/test\_import\_nptg.py                 |       31 |        0 |    100% |           |
| busstops/management/tests/test\_import\_operators.py            |       64 |        0 |    100% |           |
| busstops/middleware.py                                          |       28 |        7 |     75% |     29-43 |
| busstops/models.py                                              |      610 |       22 |     96% |275, 300, 326, 432, 469, 519, 545, 601, 635, 673, 825, 858, 929, 941-945, 1019, 1028, 1068, 1083, 1120 |
| busstops/templatetags/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| busstops/templatetags/date\_range.py                            |       25 |        3 |     88% | 9, 22, 28 |
| busstops/templatetags/urlise.py                                 |       16 |        0 |    100% |           |
| busstops/test\_admin.py                                         |       66 |        0 |    100% |           |
| busstops/test\_middleware.py                                    |       10 |        0 |    100% |           |
| busstops/test\_models.py                                        |      137 |        0 |    100% |           |
| busstops/test\_views.py                                         |      270 |        0 |    100% |           |
| busstops/urls.py                                                |       20 |        2 |     90% |   132-134 |
| busstops/utils.py                                               |       11 |        0 |    100% |           |
| busstops/views.py                                               |      643 |       50 |     92% |139, 180-189, 485, 511, 549, 694, 712, 772-775, 777, 908-913, 926, 1003, 1031-1032, 1037-1038, 1046-1055, 1116, 1212, 1233, 1235, 1261-1265, 1314, 1387, 1417-1418, 1421-1425, 1575, 1587-1588, 1593, 1605-1606 |
| bustimes/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| bustimes/admin.py                                               |      132 |       15 |     89% |65, 68-69, 75, 78-79, 82-83, 140-144, 167, 175, 188, 191, 202 |
| bustimes/download\_utils.py                                     |       32 |        0 |    100% |           |
| bustimes/fields.py                                              |       31 |        1 |     97% |        12 |
| bustimes/formatting.py                                          |       19 |        0 |    100% |           |
| bustimes/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| bustimes/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| bustimes/management/commands/bank\_holidays.py                  |       52 |        1 |     98% |       102 |
| bustimes/management/commands/import\_atco\_cif.py               |      235 |       25 |     89% |28-35, 40, 43-44, 71, 203, 205, 208, 210, 218, 224, 288, 321-326, 366-367, 434 |
| bustimes/management/commands/import\_bod\_timetables.py         |      271 |       25 |     91% |48, 99, 103, 106-109, 114, 119-120, 141, 169, 179, 191-192, 259, 269-273, 289-291, 314, 330-331, 347 |
| bustimes/management/commands/import\_gtfs.py                    |      228 |        6 |     97% |79, 131-132, 144, 151, 348 |
| bustimes/management/commands/import\_gtfs\_ember.py             |      167 |       12 |     93% |78-79, 94, 137, 142, 159, 184, 225, 236, 246, 323-324 |
| bustimes/management/commands/import\_gtfs\_flixbus.py           |      182 |        8 |     96% |76, 141, 210, 309-310, 334-335, 349 |
| bustimes/management/commands/import\_ni.py                      |       31 |        0 |    100% |           |
| bustimes/management/commands/import\_passenger.py               |      116 |       35 |     70% |51-54, 56-58, 64, 103, 113-117, 143-180 |
| bustimes/management/commands/import\_tnds.py                    |       43 |        0 |    100% |           |
| bustimes/management/commands/import\_transxchange.py            |      820 |       82 |     90% |86, 101, 147-148, 230-231, 252, 255, 308-309, 319, 327-328, 383, 387, 389, 490, 573-587, 616, 619, 737, 779-780, 817-818, 820-821, 865, 876, 914, 940, 944-946, 958-959, 1002-1006, 1047, 1057-1062, 1076, 1100, 1108, 1110-1113, 1134, 1161, 1200, 1231-1232, 1259-1261, 1268, 1273-1274, 1290, 1295, 1308, 1333, 1367-1368, 1404-1405, 1456 |
| bustimes/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| bustimes/management/tests/test\_bank\_holidays.py               |       20 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_atco\_cif.py            |       70 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_bod.py                  |      242 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs.py                 |      103 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs\_ember\_flixbus.py |       79 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_ni.py                   |       21 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_passenger.py            |       23 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_transxchange.py         |      742 |        0 |    100% |           |
| bustimes/management/tests/test\_tnds.py                         |       19 |        0 |    100% |           |
| bustimes/models.py                                              |      342 |        8 |     98% |111, 375, 378, 407, 452-455, 487 |
| bustimes/test\_get\_trip.py                                     |       31 |        0 |    100% |           |
| bustimes/tests.py                                               |      129 |        0 |    100% |           |
| bustimes/timetables.py                                          |      615 |       64 |     90% |39-52, 162-173, 204-205, 222-234, 286, 298-301, 313, 327-332, 346, 365, 440, 443, 459-462, 464, 491, 603-618, 704-705, 776, 922-924 |
| bustimes/urls.py                                                |        3 |        0 |    100% |           |
| bustimes/utils.py                                               |      178 |       10 |     94% |205, 231-233, 253-254, 323, 340-341, 389 |
| bustimes/views.py                                               |      381 |       75 |     80% |190-204, 213-215, 223-232, 234-242, 249, 271, 361, 370, 406, 412, 492, 582, 606-608, 625, 629-657, 685-696, 705-711 |
| departures/\_\_init\_\_.py                                      |        0 |        0 |    100% |           |
| departures/avl.py                                               |       12 |        1 |     92% |        14 |
| departures/gtfsr.py                                             |       91 |        2 |     98% |   91, 111 |
| departures/live.py                                              |      134 |       14 |     90% |44, 59, 61, 63, 80-85, 146, 157, 169, 183 |
| departures/sources.py                                           |      223 |       34 |     85% |34, 58, 63, 67, 100, 116, 126, 129-131, 141-148, 153-154, 168-169, 177-178, 245, 326, 343, 416, 420-421, 427-428, 431, 439 |
| departures/test\_gtfsr\_trip\_updates.py                        |       45 |        0 |    100% |           |
| departures/test\_gtfsr\_vehicle\_positions.py                   |       33 |        0 |    100% |           |
| departures/test\_live.py                                        |      111 |        0 |    100% |           |
| disruptions/\_\_init\_\_.py                                     |        0 |        0 |    100% |           |
| disruptions/admin.py                                            |       33 |        1 |     97% |        69 |
| disruptions/models.py                                           |       86 |        6 |     93% |47, 76, 100, 108, 118, 146 |
| disruptions/siri\_sx.py                                         |      124 |       14 |     89% |54, 74, 86-89, 100-101, 132, 142-146 |
| disruptions/test\_siri\_sx.py                                   |       48 |        0 |    100% |           |
| disruptions/test\_tfl\_disruptions.py                           |       34 |        0 |    100% |           |
| disruptions/tests.py                                            |       16 |        0 |    100% |           |
| disruptions/tfl\_disruptions.py                                 |       91 |        2 |     98% |    49, 85 |
| disruptions/urls.py                                             |        3 |        0 |    100% |           |
| disruptions/views.py                                            |       23 |        0 |    100% |           |
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
| transxchange/txc.py                                             |      482 |       18 |     96% |54, 125, 172, 232, 260, 306-313, 380, 382, 426, 447, 509, 542-543, 698, 729 |
| vehicles/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| vehicles/admin.py                                               |      251 |       34 |     86% |32, 60, 87, 89, 182-183, 192, 205-206, 222, 251, 254, 277, 283, 285, 287, 290, 319, 335, 341, 404-419, 432, 445, 462, 505-507 |
| vehicles/apps.py                                                |        6 |        0 |    100% |           |
| vehicles/context\_processors.py                                 |       14 |        0 |    100% |           |
| vehicles/fields.py                                              |       23 |        0 |    100% |           |
| vehicles/filters.py                                             |       20 |        0 |    100% |           |
| vehicles/form\_fields.py                                        |       15 |        0 |    100% |           |
| vehicles/forms.py                                               |       94 |        3 |     97% |130, 168, 206 |
| vehicles/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| vehicles/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| vehicles/management/commands/import\_bod\_avl.py                |      405 |       57 |     86% |51, 126, 142, 152-153, 196-199, 202-205, 248, 264, 279-280, 302-320, 371, 373, 379, 410, 416, 431-432, 476-489, 517, 524-525, 540, 569, 603, 677-678, 702, 714, 718 |
| vehicles/management/commands/import\_bushub.py                  |       83 |       18 |     78% |16-17, 21-22, 25-26, 30, 34, 42, 53, 56, 72-73, 82, 92, 111, 119, 145 |
| vehicles/management/commands/import\_edinburgh.py               |       63 |        7 |     89% |44, 72, 76-79, 81-86 |
| vehicles/management/commands/import\_gtfsr\_ember.py            |       44 |        1 |     98% |        53 |
| vehicles/management/commands/import\_gtfsr\_ie.py               |       96 |        4 |     96% |94, 140, 149, 156 |
| vehicles/management/commands/import\_live\_jersey.py            |       44 |        3 |     93% |27, 31, 39 |
| vehicles/management/commands/import\_nx.py                      |      146 |       29 |     80% |92, 109-111, 113-114, 117-118, 131, 139-146, 150-153, 167-170, 173, 185-186, 196, 207 |
| vehicles/management/commands/import\_polar.py                   |       84 |       28 |     67% |13-14, 25, 29, 33, 41, 44, 49-55, 61-63, 67, 77-78, 81, 95-98, 101, 114, 121 |
| vehicles/management/commands/import\_stagecoach\_avl.py         |       72 |        5 |     93% |124, 134, 139-140, 172 |
| vehicles/management/commands/signalr.py                         |       74 |        5 |     93% |59, 77-79, 94 |
| vehicles/management/commands/siri\_vm\_subscribe.py             |       27 |        7 |     74% |     29-58 |
| vehicles/management/import\_live\_vehicles.py                   |      333 |       55 |     83% |46, 59-75, 132, 141, 147-149, 151, 173, 202, 211-214, 223, 236, 244, 253-254, 256-257, 262-263, 277-283, 315-316, 357, 360-361, 382-383, 389, 480, 517-519, 529, 549, 556-557, 562-564 |
| vehicles/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| vehicles/management/tests/test\_bod\_avl.py                     |      293 |        0 |    100% |           |
| vehicles/management/tests/test\_bushub.py                       |       48 |        0 |    100% |           |
| vehicles/management/tests/test\_edinburgh.py                    |       49 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_live\_jersey.py         |       31 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_nx.py                   |       43 |        0 |    100% |           |
| vehicles/management/tests/test\_polar.py                        |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_signalr.py                      |       22 |        0 |    100% |           |
| vehicles/management/tests/test\_siri\_post.py                   |       51 |        0 |    100% |           |
| vehicles/management/tests/test\_stagecoach\_avl.py              |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_stats.py                        |       24 |        0 |    100% |           |
| vehicles/models.py                                              |      500 |       37 |     93% |75, 191, 216, 283, 302, 308, 380, 386, 437, 458, 573-574, 587, 595, 612-614, 622-623, 626-627, 632-633, 658, 679-683, 714, 721-724, 766, 779, 788, 804 |
| vehicles/rtpi.py                                                |       76 |        1 |     99% |        28 |
| vehicles/signals.py                                             |       11 |        0 |    100% |           |
| vehicles/tasks.py                                               |      136 |       22 |     84% |80, 85, 95, 102-105, 108, 110, 119, 132, 136-137, 155, 169, 182, 188-189, 197, 249-250, 253 |
| vehicles/test\_models.py                                        |       62 |        0 |    100% |           |
| vehicles/test\_schedule\_adherence.py                           |       75 |        0 |    100% |           |
| vehicles/tests.py                                               |      435 |        0 |    100% |           |
| vehicles/time\_aware\_polyline.py                               |       56 |       28 |     50% |18, 36, 49, 54, 57, 87-98, 106-120 |
| vehicles/urls.py                                                |        4 |        0 |    100% |           |
| vehicles/utils.py                                               |      116 |        5 |     96% |41, 144, 156-157, 161 |
| vehicles/views.py                                               |      604 |       54 |     91% |58, 351-352, 392, 419, 443-444, 463-464, 477, 495-496, 548, 566-567, 572, 588-589, 607-626, 704-705, 717, 825, 827, 829, 834, 879-880, 892-894, 981, 984-985, 995, 1011-1016, 1063-1065, 1084-1085, 1103-1113, 1117, 1119 |
| vosa/\_\_init\_\_.py                                            |        0 |        0 |    100% |           |
| vosa/admin.py                                                   |       36 |        0 |    100% |           |
| vosa/management/commands/\_\_init\_\_.py                        |        0 |        0 |    100% |           |
| vosa/management/commands/import\_vosa.py                        |      162 |        3 |     98% |25-26, 206 |
| vosa/models.py                                                  |       75 |        0 |    100% |           |
| vosa/tests.py                                                   |       60 |        0 |    100% |           |
| vosa/urls.py                                                    |        3 |        0 |    100% |           |
| vosa/views.py                                                   |       57 |        0 |    100% |           |
|                                                       **TOTAL** | **16409** | **1113** | **93%** |           |


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