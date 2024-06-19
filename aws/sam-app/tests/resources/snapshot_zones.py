POSITIVE_ZONES = {
    "hosted_zones": [
        {
            "Id": "/hostedzone/Z09090592WZ3H9FL4ISQP",
            "Name": "cbert.co.",
            "CallerReference": "b645b276-bb25-47ec-895e-af8585f974b9",
            "Config": {
                "Comment": "",
                "PrivateZone": "false"
            },
            "ResourceRecordSetCount": 10000
        },
        {
            "Id": "/hostedzone/Z07373449H5X5X4NX6X7",
            "Name": "testing.yahoo.",
            "CallerReference": "9c386bd5-341f-45da-a991-d5250a871892",
            "Config": {
                "Comment": "",
                "PrivateZone": "false"
            },
            "ResourceRecordSetCount": 10000
        },
        {
            "Id": "/hostedzone/Z014482635TU0BYFTNNCH",
            "Name": "omar.com.",
            "CallerReference": "omar.com;1716503589",
            "Config": {
                "Comment": "synced from ns1",
                "PrivateZone": "false"
            },
            "ResourceRecordSetCount": 10000
        },
        {
            "Id": "/hostedzone/Z01267492FV5DJCQZCIVI",
            "Name": "cloudsync.nsone.co.",
            "CallerReference": "d40e6811-258f-412c-be9b-7a41b69bbb2a",
            "Config": {
                "Comment": "",
                "PrivateZone": "false"
            },
            "ResourceRecordSetCount": 10000
        }
    ],
    "zones_count": 4,
    "current_zone_index": 0,
    "tags": {
        "Z02924353K4BU30DZ0RYC": {},
        "Z014482635TU0BYFTNNCH": {
            "Name": "test"
        },
        "Z01267492FV5DJCQZCIVI": {},
        "Z07373449H5X5X4NX6X7": {},
        "Z09090592WZ3H9FL4ISQP": {}
    },
    "iterator": {
        "IsTruncated": "false",
        "hosted_zones": [
            {
                "Id": "/hostedzone/Z09090592WZ3H9FL4ISQP",
                "Name": "cbert.co.",
                "CallerReference": "b645b276-bb25-47ec-895e-af8585f974b9",
                "Config": {
                    "Comment": "",
                    "PrivateZone": "false"
                },
                "ResourceRecordSetCount": 10000
            },
            {
                "Id": "/hostedzone/Z07373449H5X5X4NX6X7",
                "Name": "testing.yahoo.",
                "CallerReference": "9c386bd5-341f-45da-a991-d5250a871892",
                "Config": {
                    "Comment": "",
                    "PrivateZone": "false"
                },
                "ResourceRecordSetCount": 10000
            },
            {
                "Id": "/hostedzone/Z014482635TU0BYFTNNCH",
                "Name": "omar.com.",
                "CallerReference": "omar.com;1716503589",
                "Config": {
                    "Comment": "synced from ns1",
                    "PrivateZone": "false"
                },
                "ResourceRecordSetCount": 10000
            },
            {
                "Id": "/hostedzone/Z01267492FV5DJCQZCIVI",
                "Name": "cloudsync.nsone.co.",
                "CallerReference": "d40e6811-258f-412c-be9b-7a41b69bbb2a",
                "Config": {
                    "Comment": "",
                    "PrivateZone": "false"
                },
                "ResourceRecordSetCount": 10000
            }
        ],
        "zones_count": 4,
        "current_zone_index": 2
    }
}

OMIT_ZONES = {
    "hosted_zones": [

        {
            "Id": "/hostedzone/Z014482635TU0BYFTNNCH",
            "Name": "omar.com.",
            "CallerReference": "omar.com;1716503589",
            "Config": {
                "Comment": "synced from ns1",
                "PrivateZone": "false"
            },
            "ResourceRecordSetCount": 10000
        }
    ],
    "zones_count": 1,
    "current_zone_index": 0,
    "tags": {
        "Z014482635TU0BYFTNNCH": {
            'ENABLE_ZONE_OMIT': 'True',
            'ZONE_OMIT_TAG': 'CloudSync',
            'Name': "foo12"
        },
    },
    "iterator": {
        "IsTruncated": "false",
        "hosted_zones": [
            {
                "Id": "/hostedzone/Z014482635TU0BYFTNNCH",
                "Name": "omar.com.",
                "CallerReference": "omar.com;1716503589",
                "Config": {
                    "Comment": "synced from ns1",
                    "PrivateZone": "false"
                },
                "ResourceRecordSetCount": 10000
            },
        ],
        "zones_count": 1,
        "current_zone_index": 0
    }
}
