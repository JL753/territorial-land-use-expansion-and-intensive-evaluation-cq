#!/usr/bin/env sh
set -eu
root=$(cd "$(dirname "$0")/../../.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/assets" "$root/downloads"
cp "$root/clients/desktop/portable/main.go" "$work/"
cp -r "$root"/web/* "$work/assets/"
cp "$root/results/socioeconomic/four-year-exploratory/dashboard.json" "$root/results/socioeconomic/four-year-exploratory/districts.geojson" "$work/assets/"
cp "$root/results/analysis/report.json" "$work/assets/analysis-report.json"
cd "$work"
export GO111MODULE=off CGO_ENABLED=0 GOARCH=amd64
GOOS=windows go build -trimpath -ldflags="-s -w -H windowsgui" -o "$root/downloads/cq-land-windows.exe" main.go
GOOS=linux go build -trimpath -ldflags="-s -w" -o "$root/downloads/cq-land-linux" main.go
