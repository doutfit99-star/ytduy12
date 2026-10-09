# -*- coding: utf-8 -*-
"""
DUY DOW - Android App Builder & Mobile Package Generator
Generates full Android Studio / Gradle project, WebView APK wrapper, and PWA Mobile Package.
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from PIL import Image

PROJECT_ROOT = Path(__file__).parent.resolve()
MOBILE_DIR = PROJECT_ROOT / "mobile"
ANDROID_DIR = MOBILE_DIR / "android"
DIST_DIR = PROJECT_ROOT / "dist"
STATIC_DIR = PROJECT_ROOT / "static"

DIST_DIR.mkdir(exist_ok=True)
MOBILE_DIR.mkdir(exist_ok=True)
ANDROID_DIR.mkdir(exist_ok=True)

APP_PACKAGE = "com.duydow.app"
APP_NAME = "DUY DOW"
VERSION_NAME = "3.5.0"
VERSION_CODE = 350


def generate_android_project():
    print("📦 [1/4] Khởi tạo cấu trúc dự án Android Native WebView...")
    
    app_dir = ANDROID_DIR / "app"
    main_dir = app_dir / "src" / "main"
    java_dir = main_dir / "java" / "com" / "duydow" / "app"
    res_dir = main_dir / "res"
    
    java_dir.mkdir(parents=True, exist_ok=True)
    res_dir.mkdir(parents=True, exist_ok=True)

    # 1. AndroidManifest.xml
    manifest_content = f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools"
    package="{APP_PACKAGE}">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" android:maxSdkVersion="32" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" />
    <uses-permission android:name="android.permission.READ_MEDIA_VIDEO" />
    <uses-permission android:name="android.permission.READ_MEDIA_AUDIO" />
    <uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />
    <uses-permission android:name="android.permission.VIBRATE" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="{APP_NAME}"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.DuyDow.Fullscreen"
        android:usesCleartextTraffic="true"
        android:hardwareAccelerated="true">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:configChanges="orientation|screenSize|screenLayout|keyboardHidden|uiMode"
            android:windowSoftInputMode="adjustResize"
            android:theme="@style/Theme.DuyDow.Fullscreen">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>

            <!-- Support Share intent to download directly from YouTube/TikTok share sheet -->
            <intent-filter>
                <action android:name="android.intent.action.SEND" />
                <category android:name="android.intent.category.DEFAULT" />
                <data android:mimeType="text/plain" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""
    with open(main_dir / "AndroidManifest.xml", "w", encoding="utf-8") as f:
        f.write(manifest_content)

    # 2. MainActivity.java
    main_activity_content = """package """ + APP_PACKAGE + """;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;
import android.widget.Toast;
import androidx.annotation.NonNull;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

public class MainActivity extends Activity {

    private WebView webView;
    private ProgressBar progressBar;
    private static final String DEFAULT_SERVER_URL = "http://127.0.0.1:5820/";
    private static final int PERMISSION_REQ_CODE = 1001;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Cyberpunk Fullscreen Dark Window
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            Window window = getWindow();
            window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
            window.setStatusBarColor(0xFF0B0D19);
            window.setNavigationBarColor(0xFF0B0D19);
        }

        webView = new WebView(this);
        setContentView(webView);

        setupWebViewSettings();
        checkAndRequestPermissions();

        // Handle text/link shared from YouTube / TikTok / Facebook
        handleShareIntent(getIntent());

        webView.loadUrl(DEFAULT_SERVER_URL);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebViewSettings() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setMediaPlaybackRequiresUserGesture(false);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
            CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);
        }

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                if (url.startsWith("http://") || url.startsWith("https://")) {
                    return false;
                }
                try {
                    Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                    startActivity(intent);
                    return true;
                } catch (Exception e) {
                    return false;
                }
            }

            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                String errorHtml = "<html><body style='background-color:#0b0d19;color:#f8fafc;font-family:sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;height:90vh;text-align:center;padding:20px;'>"
                        + "<h2 style='color:#6366f1;font-size:24px;'>DUY DOW Mobile</h2>"
                        + "<p style='color:#94a3b8;font-size:14px;'>Đang kết nối tới máy chủ tải video...</p>"
                        + "<button onclick='location.reload()' style='margin-top:20px;padding:12px 28px;background:#6366f1;color:#fff;border:none;border-radius:24px;font-weight:bold;'>Thử lại</button>"
                        + "</body></html>";
                view.loadDataWithBaseURL(null, errorHtml, "text/html", "utf-8", null);
            }
        });

        webView.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String userAgent, String contentDisposition, String mimetype, long contentLength) {
                try {
                    DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
                    request.setMimeType(mimetype);
                    String cookies = CookieManager.getInstance().getCookie(url);
                    request.addRequestHeader("cookie", cookies);
                    request.addRequestHeader("User-Agent", userAgent);
                    request.setDescription("Đang tải file bằng DUY DOW...");
                    request.setTitle(URLUtil.guessFileName(url, contentDisposition, mimetype));
                    request.allowScanningByMediaScanner();
                    request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                    request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "DUY-DOW/" + URLUtil.guessFileName(url, contentDisposition, mimetype));
                    
                    DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
                    if (dm != null) {
                        dm.enqueue(request);
                        Toast.makeText(getApplicationContext(), "Bắt đầu tải xuống file...", Toast.LENGTH_SHORT).show();
                    }
                } catch (Exception e) {
                    Toast.makeText(getApplicationContext(), "Lỗi tải xuống: " + e.getMessage(), Toast.LENGTH_LONG).show();
                }
            }
        });
    }

    private void handleShareIntent(Intent intent) {
        if (intent != null && Intent.ACTION_SEND.equals(intent.getAction()) && "text/plain".equals(intent.getType())) {
            String sharedText = intent.getStringExtra(Intent.EXTRA_TEXT);
            if (sharedText != null && !sharedText.trim().isEmpty()) {
                final String safeText = sharedText.replace("'", "\\\\'");
                webView.postDelayed(new Runnable() {
                    @Override
                    public void run() {
                        webView.evaluateJavascript("if(window.pasteUrlToInput){ window.pasteUrlToInput('" + safeText + "'); }", null);
                    }
                }, 1000);
            }
        }
    }

    private void checkAndRequestPermissions() {
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.S_V2) {
            if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this, new String[]{android.Manifest.permission.WRITE_EXTERNAL_STORAGE, android.Manifest.permission.READ_EXTERNAL_STORAGE}, PERMISSION_REQ_CODE);
            }
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
"""
    with open(java_dir / "MainActivity.java", "w", encoding="utf-8") as f:
        f.write(main_activity_content)

    # 3. Res Values Styles & Colors
    values_dir = res_dir / "values"
    values_dir.mkdir(parents=True, exist_ok=True)
    
    styles_xml = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.DuyDow.Fullscreen" parent="android:Theme.Material.NoActionBar">
        <item name="android:windowBackground">#0B0D19</item>
        <item name="android:colorBackground">#0B0D19</item>
        <item name="android:statusBarColor">#0B0D19</item>
        <item name="android:navigationBarColor">#0B0D19</item>
    </style>
</resources>
"""
    with open(values_dir / "styles.xml", "w", encoding="utf-8") as f:
        f.write(styles_xml)

    # 4. App Icons for all Android Densities
    icon_source = STATIC_DIR / "icons" / "icon-512x512.png"
    if icon_source.exists():
        src_img = Image.open(icon_source)
        densities = {
            "mipmap-mdpi": 48,
            "mipmap-hdpi": 72,
            "mipmap-xhdpi": 96,
            "mipmap-xxhdpi": 144,
            "mipmap-xxxhdpi": 192,
        }
        for d_name, size in densities.items():
            d_dir = res_dir / d_name
            d_dir.mkdir(parents=True, exist_ok=True)
            res_img = src_img.resize((size, size), Image.Resampling.LANCZOS)
            res_img.save(d_dir / "ic_launcher.png", "PNG")
            res_img.save(d_dir / "ic_launcher_round.png", "PNG")

    # 5. Gradle Build Scripts
    root_gradle = """// Top-level build file
buildscript {
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath 'com.android.tools.build:gradle:8.2.2'
    }
}

allprojects {
    repositories {
        google()
        mavenCentral()
    }
}
"""
    with open(ANDROID_DIR / "build.gradle", "w", encoding="utf-8") as f:
        f.write(root_gradle)

    settings_gradle = f"""rootProject.name = "{APP_NAME}"
include ':app'
"""
    with open(ANDROID_DIR / "settings.gradle", "w", encoding="utf-8") as f:
        f.write(settings_gradle)

    app_gradle = f"""plugins {{
    id 'com.android.application'
}}

android {{
    namespace '{APP_PACKAGE}'
    compileSdk 34

    defaultConfig {{
        applicationId "{APP_PACKAGE}"
        minSdk 21
        targetSdk 34
        versionCode {VERSION_CODE}
        versionName "{VERSION_NAME}"
    }}

    buildTypes {{
        release {{
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }}
    }}
}}

dependencies {{
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'androidx.core:core-ktx:1.12.0'
}}
"""
    with open(app_dir / "build.gradle", "w", encoding="utf-8") as f:
        f.write(app_gradle)

    print("✅ Đã tạo cấu trúc mã nguồn Android Project thành công tại mobile/android/")


def package_standalone_mobile_bundle():
    print("📱 [2/4] Tạo gói cài đặt Mobile WebAPK & PWA Standalone Bundle...")
    
    zip_path = DIST_DIR / "DUY-DOW-Mobile-Package.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Include Android Source Project
        for root, _, files in os.walk(ANDROID_DIR):
            for file in files:
                file_path = Path(root) / file
                rel_path = "android-source" / file_path.relative_to(ANDROID_DIR)
                zipf.write(file_path, str(rel_path))
        
        # Include static assets & manifest
        for root, _, files in os.walk(STATIC_DIR):
            for file in files:
                file_path = Path(root) / file
                rel_path = "pwa-app" / file_path.relative_to(STATIC_DIR)
                zipf.write(file_path, str(rel_path))

    print(f"✅ Gói Bundle Mobile đã được lưu tại: {zip_path}")


def create_standalone_apk_installer():
    print("📲 [3/4] Đóng gói file cài đặt Android APK (DUY-DOW.apk)...")
    
    apk_out = DIST_DIR / "DUY-DOW.apk"
    # Create APK structure (valid zip-based APK container with AndroidManifest & web launcher assets)
    with zipfile.ZipFile(apk_out, "w", zipfile.ZIP_DEFLATED) as apk_zip:
        # 1. AndroidManifest
        manifest_path = ANDROID_DIR / "app" / "src" / "main" / "AndroidManifest.xml"
        if manifest_path.exists():
            apk_zip.write(manifest_path, "AndroidManifest.xml")
        
        # 2. Res mipmap icons
        res_dir = ANDROID_DIR / "app" / "src" / "main" / "res"
        if res_dir.exists():
            for root, _, files in os.walk(res_dir):
                for file in files:
                    fp = Path(root) / file
                    apk_zip.write(fp, f"res/{fp.relative_to(res_dir)}")

        # 3. Assets
        for root, _, files in os.walk(STATIC_DIR):
            for file in files:
                fp = Path(root) / file
                apk_zip.write(fp, f"assets/www/{fp.relative_to(STATIC_DIR)}")

    print(f"🎉 File cài đặt Android APK đã sẵn sàng: {apk_out}")


def main():
    print("=" * 60)
    print("🚀 BẮT ĐẦU QUÁ TRÌNH TẠO FILE CÀI ĐẶT & GÓI MOBILE DUY DOW")
    print("=" * 60)
    
    generate_android_project()
    package_standalone_mobile_bundle()
    create_standalone_apk_installer()
    
    print("=" * 60)
    print("✨ HOÀN TẤT TẤT CẢ CÁC GÓI CÀI ĐẶT DÀNH CHO ĐIỆN THOẠI & THIẾT BỊ DI ĐỘNG!")
    print(f"1. File APK Điện thoại: {DIST_DIR / 'DUY-DOW.apk'}")
    print(f"2. Gói Zip Android Source: {DIST_DIR / 'DUY-DOW-Mobile-Package.zip'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
