package cn.cqland.studio;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

public class StudyActivity extends Activity {
    private static final int EXPORT = 21;
    private static final String HOST = "appassets.androidplatform.net";
    private static final Set<String> ASSETS = new HashSet<>(Arrays.asList(
        "index.html","app.js","analysis.js","style.css","icon192.png","icon512.png",
        "dashboard.json","districts.geojson","manifest.webmanifest"));
    private String pendingCsv;
    private WebView web;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (state != null) pendingCsv = state.getString("csv");
        web = new WebView(this);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.addJavascriptInterface(new ExportActions(), "CQLandAndroid");
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String path = uri.getPath();
                if (HOST.equals(uri.getHost()) && "https".equals(uri.getScheme()) && path != null) {
                    if (path.equals("/api/config"))
                        return new WebResourceResponse("application/json","utf-8",new ByteArrayInputStream("{}".getBytes(StandardCharsets.UTF_8)));
                    String file = path.equals("/") ? "index.html" : path.substring(1);
                    if (ASSETS.contains(file)) {
                        String mime = file.endsWith(".js") ? "text/javascript" : file.endsWith(".css") ? "text/css" :
                            file.endsWith(".png") ? "image/png" : file.endsWith(".html") ? "text/html" : "application/json";
                        try { return new WebResourceResponse(mime, "utf-8", getAssets().open(file)); }
                        catch (IOException ignored) { }
                    }
                }
                return new WebResourceResponse("text/plain","utf-8",404,"Not Found",null,null);
            }
        });
        // Keep the layout clear of system bars on edge-to-edge Android releases.
        web.setOnApplyWindowInsetsListener((view,insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),
                insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
            return insets;
        });
        setContentView(web);
        web.loadUrl("https://" + HOST + "/");
    }

    private class ExportActions {
        @JavascriptInterface public void saveCsv(String name, String content) {
            runOnUiThread(() -> {
                pendingCsv = content;
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("text/csv");
                intent.putExtra(Intent.EXTRA_TITLE, name);
                startActivityForResult(intent, EXPORT);
            });
        }
        @JavascriptInterface public void fullscreen() {
            runOnUiThread(() -> web.setSystemUiVisibility(web.getSystemUiVisibility() == 0 ? 5894 : 0));
        }
    }
    @Override public void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        out.putString("csv", pendingCsv);
    }
    @Override public void onActivityResult(int request, int result, Intent intent) {
        super.onActivityResult(request, result, intent);
        if (request == EXPORT && result == RESULT_OK && intent != null && intent.getData() != null && pendingCsv != null) {
            try (OutputStream stream = getContentResolver().openOutputStream(intent.getData())) {
                if (stream == null) throw new IOException();
                stream.write(pendingCsv.getBytes(StandardCharsets.UTF_8));
            } catch (IOException ex) { Toast.makeText(this, "导出失败，请重试", Toast.LENGTH_LONG).show(); }
        }
        pendingCsv = null;
    }
}
