# Reachability Demo data

`demo.geojson` (generated `2026-08-02T00:00:00+08:00`) is a small, fixed
competition fixture for the venue `華南銀行國際會議中心（臺北市信義區松仁路
123 號）`.  It is intentionally labelled as an internal Demo approximation:
it is useful for showing the interaction and Catalog filtering, but it is not
an official coordinate, live traffic result, or navigation route.

The metadata records `source`, `generatedAt`, `reviewStatus`,
`coordinateStatus`, `isDemo`, `realTime`, and `navigation`.  Keep
`isDemo: true`, `realTime: false`, and `navigation: false` so the UI never
overstates what the fixture proves.

When the external evidence is available, add features keyed by:

- `originId`
- `travelMode`: `pedestrian` or `scooter`
- `thresholdMinutes`: `10` or `15`
- `eligibleLocationIds`

The file must retain `isDemo: true`, `realTime: false`, and `navigation: false`
for the competition fallback.
