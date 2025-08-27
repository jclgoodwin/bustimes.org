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
| api/views.py                                                    |       94 |        0 |    100% |           |
| buses/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| buses/context\_processors.py                                    |        5 |        0 |    100% |           |
| buses/jinja2.py                                                 |       36 |        2 |     94% |    40, 61 |
| buses/settings.py                                               |      123 |       31 |     75% |96-105, 122, 141-149, 205, 224-232, 249-265, 317 |
| buses/tests.py                                                  |        5 |        0 |    100% |           |
| buses/urls.py                                                   |        5 |        0 |    100% |           |
| buses/utils.py                                                  |       23 |        4 |     83% |     34-37 |
| busstops/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| busstops/admin.py                                               |      318 |       16 |     95% |103-109, 184, 243-251, 333-334, 380, 455, 459, 508, 542, 586, 590, 614, 618 |
| busstops/forms.py                                               |       46 |        0 |    100% |           |
| busstops/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| busstops/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| busstops/management/commands/import\_noc.py                     |      125 |        3 |     98% |155, 179, 238 |
| busstops/management/commands/naptan\_new.py                     |      160 |       10 |     94% |39, 41, 165-173, 214, 263 |
| busstops/management/commands/nptg\_new.py                       |       94 |        7 |     93% |148, 158, 163, 169-170, 172-173 |
| busstops/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| busstops/management/tests/test\_import\_ie.py                   |       63 |        0 |    100% |           |
| busstops/management/tests/test\_import\_naptan.py               |       67 |        0 |    100% |           |
| busstops/management/tests/test\_import\_nptg.py                 |       31 |        0 |    100% |           |
| busstops/management/tests/test\_import\_operators.py            |       64 |        0 |    100% |           |
| busstops/middleware.py                                          |       28 |        7 |     75% |     29-43 |
| busstops/models.py                                              |      626 |       25 |     96% |275, 321, 427, 464, 514, 540, 630, 668, 820, 862-866, 871, 882, 901-902, 970, 982-986, 1041, 1048, 1088, 1103, 1140 |
| busstops/templatetags/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| busstops/templatetags/date\_range.py                            |       25 |        3 |     88% | 9, 22, 28 |
| busstops/templatetags/urlise.py                                 |       16 |        0 |    100% |           |
| busstops/test\_admin.py                                         |       52 |        0 |    100% |           |
| busstops/test\_middleware.py                                    |       10 |        0 |    100% |           |
| busstops/test\_models.py                                        |      143 |        0 |    100% |           |
| busstops/test\_views.py                                         |      270 |        0 |    100% |           |
| busstops/urls.py                                                |       20 |        2 |     90% |   136-138 |
| busstops/utils.py                                               |       11 |        0 |    100% |           |
| busstops/views.py                                               |      637 |       49 |     92% |121, 162-171, 465, 491, 529, 674, 692, 752-755, 757, 888-893, 906, 983, 1011-1012, 1017-1018, 1026-1035, 1188, 1209, 1211, 1237-1241, 1290, 1363, 1393-1394, 1397-1401, 1551, 1563-1564, 1569, 1581-1582 |
| bustimes/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| bustimes/admin.py                                               |      113 |       15 |     87% |64, 67-68, 74, 77-78, 81-82, 139-143, 166, 174, 187, 190, 201 |
| bustimes/download\_utils.py                                     |       32 |        0 |    100% |           |
| bustimes/fields.py                                              |       31 |        1 |     97% |        12 |
| bustimes/formatting.py                                          |       19 |        0 |    100% |           |
| bustimes/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| bustimes/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| bustimes/management/commands/bank\_holidays.py                  |       52 |        1 |     98% |       102 |
| bustimes/management/commands/import\_atco\_cif.py               |      235 |       25 |     89% |28-35, 40, 43-44, 71, 203, 205, 208, 210, 218, 224, 288, 321-326, 366-367, 434 |
| bustimes/management/commands/import\_bod\_timetables.py         |      271 |       25 |     91% |48, 97, 101, 104-107, 112, 117-118, 139, 167, 177, 189-190, 257, 267-271, 287-289, 312, 328-329, 345 |
| bustimes/management/commands/import\_gtfs.py                    |      237 |       23 |     90% |78, 82, 132-133, 145, 152, 224, 226, 286-287, 289-290, 326-327, 333-334, 338-341, 349-351, 415 |
| bustimes/management/commands/import\_gtfs\_ember.py             |      103 |        6 |     94% |66-67, 82, 125, 130, 166 |
| bustimes/management/commands/import\_gtfs\_flixbus.py           |      144 |        3 |     98% |75, 142, 210 |
| bustimes/management/commands/import\_ni.py                      |       31 |        0 |    100% |           |
| bustimes/management/commands/import\_passenger.py               |      116 |       34 |     71% |51-54, 56-58, 102, 112-116, 142-179 |
| bustimes/management/commands/import\_tnds.py                    |       43 |        0 |    100% |           |
| bustimes/management/commands/import\_transxchange.py            |      780 |       77 |     90% |84, 96, 142-143, 291, 374-388, 417, 420, 538, 580-581, 618-619, 621-622, 645-646, 656, 664-665, 725, 736, 772, 798, 802-804, 856-860, 921, 925, 927, 940-945, 982-983, 994, 1012, 1020, 1022-1025, 1048, 1075, 1114, 1145-1146, 1173-1175, 1182, 1187-1188, 1199, 1204, 1217, 1242, 1276-1277, 1313-1314, 1383 |
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
| bustimes/models.py                                              |      340 |        9 |     97% |111, 214, 372, 375, 404, 449-452, 484 |
| bustimes/test\_get\_trip.py                                     |       31 |        0 |    100% |           |
| bustimes/tests.py                                               |      132 |        0 |    100% |           |
| bustimes/timetables.py                                          |      637 |       53 |     92% |101-114, 143, 229-240, 271-272, 332, 344-347, 359, 373-378, 392, 411, 486, 489, 505-508, 510, 537, 646-661, 747-748, 819, 965-967 |
| bustimes/urls.py                                                |        3 |        0 |    100% |           |
| bustimes/utils.py                                               |      189 |       10 |     95% |228, 254-256, 276-277, 346, 363-364, 412 |
| bustimes/views.py                                               |      369 |       75 |     80% |162-176, 185-187, 195-204, 206-214, 221, 243, 333, 342, 378, 384, 464, 554, 578-580, 597, 601-629, 657-668, 677-683 |
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
| disruptions/siri\_sx.py                                         |      122 |       14 |     89% |58, 78, 90-93, 104-105, 136, 146-150 |
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
| vehicles/management/commands/import\_bod\_avl.py                |      405 |       57 |     86% |51, 126, 142, 152-153, 196-199, 202-205, 248, 264, 279-280, 302-320, 371, 373, 379, 410, 416, 431-432, 476-489, 517, 524-525, 540, 569, 603, 677-678, 701, 713, 717 |
| vehicles/management/commands/import\_bushub.py                  |       83 |       18 |     78% |16-17, 21-22, 25-26, 30, 34, 42, 53, 56, 72-73, 82, 92, 111, 119, 145 |
| vehicles/management/commands/import\_edinburgh.py               |       63 |        7 |     89% |44, 72, 76-79, 81-86 |
| vehicles/management/commands/import\_gtfsr\_ember.py            |       66 |        3 |     95% | 67-68, 93 |
| vehicles/management/commands/import\_gtfsr\_ie.py               |       97 |        5 |     95% |94, 140, 149, 156, 160 |
| vehicles/management/commands/import\_live\_jersey.py            |       44 |        3 |     93% |27, 31, 39 |
| vehicles/management/commands/import\_nx.py                      |      146 |       29 |     80% |92, 109-111, 113-114, 117-118, 131, 139-146, 150-153, 167-170, 173, 185-186, 196, 207 |
| vehicles/management/commands/import\_polar.py                   |       84 |       28 |     67% |13-14, 25, 29, 33, 41, 44, 49-55, 61-63, 67, 77-78, 81, 95-98, 101, 114, 121 |
| vehicles/management/commands/import\_stagecoach\_avl.py         |       72 |        5 |     93% |124, 134, 139-140, 172 |
| vehicles/management/commands/signalr.py                         |       74 |        5 |     93% |59, 76-78, 93 |
| vehicles/management/commands/siri\_vm\_subscribe.py             |       26 |        7 |     73% |     27-55 |
| vehicles/management/import\_live\_vehicles.py                   |      330 |       53 |     84% |45, 58-74, 131, 140, 146-148, 150, 172, 201, 210-213, 222, 235, 243, 252-253, 255-256, 261-262, 276-282, 314-315, 356, 359-360, 381-382, 388, 479, 516-518, 528, 547, 557-559 |
| vehicles/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| vehicles/management/tests/test\_bod\_avl.py                     |      294 |        0 |    100% |           |
| vehicles/management/tests/test\_bushub.py                       |       48 |        0 |    100% |           |
| vehicles/management/tests/test\_edinburgh.py                    |       49 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_live\_jersey.py         |       31 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_nx.py                   |       43 |        0 |    100% |           |
| vehicles/management/tests/test\_polar.py                        |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_signalr.py                      |       22 |        0 |    100% |           |
| vehicles/management/tests/test\_siri\_post.py                   |       40 |        0 |    100% |           |
| vehicles/management/tests/test\_stagecoach\_avl.py              |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_stats.py                        |       24 |        0 |    100% |           |
| vehicles/models.py                                              |      500 |       37 |     93% |75, 191, 216, 287, 306, 312, 384, 390, 441, 462, 577-578, 591, 599, 616-618, 626-627, 630-631, 636-637, 662, 683-687, 718, 725-728, 770, 783, 792, 808 |
| vehicles/rtpi.py                                                |       76 |        1 |     99% |        28 |
| vehicles/signals.py                                             |       11 |        0 |    100% |           |
| vehicles/tasks.py                                               |      138 |       22 |     84% |82, 87, 97, 104-107, 110, 112, 121, 134, 138-139, 157, 171, 184, 190-191, 199, 251-252, 255 |
| vehicles/test\_models.py                                        |       62 |        0 |    100% |           |
| vehicles/test\_schedule\_adherence.py                           |       75 |        0 |    100% |           |
| vehicles/tests.py                                               |      435 |        0 |    100% |           |
| vehicles/time\_aware\_polyline.py                               |       56 |       28 |     50% |18, 36, 49, 54, 57, 87-98, 106-120 |
| vehicles/urls.py                                                |        4 |        0 |    100% |           |
| vehicles/utils.py                                               |      128 |        6 |     95% |41-42, 155, 167-168, 172 |
| vehicles/views.py                                               |      580 |       55 |     91% |345-346, 397, 424, 439-440, 459-460, 473, 491-492, 538, 556-557, 559, 564, 580-581, 599-618, 696-697, 704, 718, 826, 828, 830, 835, 880-881, 893-895, 982, 985-986, 996, 1012-1017, 1058-1059, 1105, 1173-1211 |
| vosa/\_\_init\_\_.py                                            |        0 |        0 |    100% |           |
| vosa/admin.py                                                   |       36 |        0 |    100% |           |
| vosa/management/commands/\_\_init\_\_.py                        |        0 |        0 |    100% |           |
| vosa/management/commands/import\_vosa.py                        |      162 |        3 |     98% |25-26, 206 |
| vosa/models.py                                                  |       75 |        0 |    100% |           |
| vosa/tests.py                                                   |       60 |        0 |    100% |           |
| vosa/urls.py                                                    |        3 |        0 |    100% |           |
| vosa/views.py                                                   |       57 |        0 |    100% |           |
|                                                       **TOTAL** | **16255** | **1106** | **93%** |           |


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