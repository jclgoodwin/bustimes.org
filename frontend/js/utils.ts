import { LngLatBounds } from "maplibre-gl";

export function getBounds<T>(
  list: Array<T> | undefined,
  key: (arg0: T) => [number, number] | null | undefined,
  initialBounds?: LngLatBounds,
) {
  if (list?.length) {
    const bounds = initialBounds || new LngLatBounds();
    list.reduce((bounds, item?) => {
      if (item) {
        const value = key(item);
        if (value) {
          bounds.extend(value);
        }
      }
      return bounds;
    }, bounds);
    return bounds;
  }
}
