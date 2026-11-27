#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
sdk=${ANDROID_HOME:?set ANDROID_HOME to an Android SDK with API 35}
tools="$sdk/build-tools/35.0.0"
platform="$sdk/platforms/android-35/android.jar"
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT
mkdir -p "$build"/{assets/city,res/drawable,classes} "$root/downloads"
cp "$root"/web/{mobile.html,mobile.css,mobile.js,live.js,live.css,analysis.js,client-utils.js,mobile.webmanifest,river-ink.webp,icon192.png,icon512.png} "$build/assets/"
cp "$root"/results/socioeconomic/four-year-exploratory/dashboard.json "$build/assets/"
cp "$root/web/city/manifest.json" "$build/assets/city/manifest.json"
cp "$root/web/icon192.png" "$build/res/drawable/land_icon.png"
"$tools/aapt2" compile --dir "$build/res" -o "$build/res.zip"
"$tools/aapt2" link -o "$build/app.apk" -I "$platform" --manifest "$root/clients/android/AndroidManifest.xml" -A "$build/assets" "$build/res.zip"
javac -encoding UTF-8 --release 8 -classpath "$platform" -d "$build/classes" "$root/clients/android/src/cn/cqland/studio/StudyActivity.java"
jar cf "$build/classes.jar" -C "$build/classes" .
"$tools/d8" --min-api 26 --lib "$platform" --output "$build" "$build/classes.jar"
(cd "$build" && zip -q app.apk classes.dex)
"$tools/zipalign" -f 4 "$build/app.apk" "$build/aligned.apk"
# Development signing identity. Supply an existing keystore to keep upgrade compatibility.
store=${CQ_ANDROID_KEYSTORE:-$build/demo.p12}
if [[ ! -f "$store" ]]; then
 keytool -genkeypair -keystore "$store" -storepass android -keypass android -alias cqdemo -keyalg RSA -keysize 3072 -validity 3650 -dname "CN=CQ Land Research Demo"
fi
"$tools/apksigner" sign --ks "$store" --ks-pass pass:android --out "$root/downloads/cq-land-android.apk" "$build/aligned.apk"
"$tools/apksigner" verify --verbose "$root/downloads/cq-land-android.apk"
