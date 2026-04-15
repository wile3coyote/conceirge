package com.example.conceirge.data

import android.content.Context

private const val PREFS_NAME = "concierge_prefs"
private const val KEY_BASE_URL = "base_url"

object UrlStore {
    fun getUrl(context: Context): String? =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString(KEY_BASE_URL, null)

    fun saveUrl(context: Context, url: String) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_BASE_URL, url.trimEnd('/'))
            .apply()
    }

    fun clearUrl(context: Context) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .remove(KEY_BASE_URL)
            .apply()
    }
}
