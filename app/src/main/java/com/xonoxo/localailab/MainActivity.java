package com.xonoxo.localailab;

import android.app.Activity;
import android.os.Bundle;
import android.os.Build;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setTitle("LocalAI Lab");

        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(24), dp(20), dp(24));
        scroll.addView(root, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        TextView title = text("LocalAI Lab", 28, true);
        title.setGravity(Gravity.START);
        root.addView(title);

        TextView subtitle = text("Disposable Android shell for local AI experiments.", 15, false);
        subtitle.setPadding(0, dp(6), 0, dp(18));
        root.addView(subtitle);

        addCard(root, "Status", "Installed and launched successfully.");
        addCard(root, "Build", getBuildInfo());
        addCard(root, "Runtime", "No local inference runtime is wired yet.");
        addCard(root, "Model files", "Not configured yet. Future builds will add model selection and storage checks.");
        addCard(root, "Next", "Keep the APK delivery loop stable, then choose the first local inference backend.");

        setContentView(scroll);
    }

    private String getBuildInfo() {
        String versionName = "unknown";
        long versionCode = 0;
        try {
            PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0);
            versionName = info.versionName;
            if (Build.VERSION.SDK_INT >= 28) {
                versionCode = info.getLongVersionCode();
            } else {
                versionCode = info.versionCode;
            }
        } catch (PackageManager.NameNotFoundException ignored) {
        }
        return "Version: " + versionName + "\n"
                + "Version code: " + versionCode + "\n"
                + "Package: " + getPackageName() + "\n"
                + "Android: " + Build.VERSION.RELEASE + " / API " + Build.VERSION.SDK_INT;
    }

    private void addCard(LinearLayout root, String heading, String body) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(14), dp(16), dp(14));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(0, 0, 0, dp(12));
        card.setLayoutParams(params);
        card.setBackgroundColor(0xFFF3F4F6);

        TextView h = text(heading, 17, true);
        h.setPadding(0, 0, 0, dp(6));
        card.addView(h);

        TextView b = text(body, 14, false);
        b.setLineSpacing(0, 1.15f);
        card.addView(b);

        root.addView(card);
    }

    private TextView text(String value, int sp, boolean bold) {
        TextView tv = new TextView(this);
        tv.setText(value);
        tv.setTextSize(sp);
        tv.setTextColor(0xFF111827);
        if (bold) tv.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return tv;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
