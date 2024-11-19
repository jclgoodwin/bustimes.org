function getDecodedDimensionFromPolyline(polyline: string, index: number) {
    let result = 1,
        shift = 0,
        b;

    while (
        (b = polyline.charCodeAt(index) - 64) >= 0x1F
    ) {
        console.log(b);
        index += 1;
        result += b << shift;
        shift += 5;
    }
    return [index, (result & 1) !== 0 ? ~result >> 1 : result >> 1];
}

export function decodeTimeAwarePolyline(polyline: string) {
    let index = 0,
        lat = 0,
        lng = 0,
        timestamp = 0;
    const response = [];

    const length = polyline.length;

    while (index < length) {
        let lat_diff = 0, lng_diff, timestamp_diff;

        [index, lng_diff] = getDecodedDimensionFromPolyline(polyline, index);
        [index, lat_diff] = getDecodedDimensionFromPolyline(polyline, index);
        [index, timestamp_diff] = getDecodedDimensionFromPolyline(polyline, index);

        lng += lng_diff;
        lat += lat_diff;
        timestamp += timestamp_diff;

        response.push([lat * 1e-5, lng * 1e-5, timestamp * 1000]);
    }
    return response;
}
