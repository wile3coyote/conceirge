package com.example.conceirge.data.cache

import android.content.Context
import android.util.Log
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.example.conceirge.data.models.LibraryItem
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.flow.first

private val Context.libraryDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "library_cache"
)

private const val TAG = "LibraryCache"
private val KEY_LIBRARY_JSON = stringPreferencesKey("library_json")

class LibraryCache(private val context: Context) {

    private val gson = Gson()
    private val listType = object : TypeToken<List<LibraryItem>>() {}.type

    /**
     * Returns the last-saved library list, or an empty list if the cache is empty
     * or the stored JSON cannot be parsed.
     */
    suspend fun load(): List<LibraryItem> {
        val json = context.libraryDataStore.data
            .first()[KEY_LIBRARY_JSON]
            ?: return emptyList()

        return try {
            gson.fromJson(json, listType) ?: emptyList()
        } catch (e: Exception) {
            Log.w(TAG, "Failed to parse cached library JSON; returning empty list", e)
            emptyList()
        }
    }

    /**
     * Persists [items] to DataStore as a JSON string, replacing any previous value.
     */
    suspend fun save(items: List<LibraryItem>) {
        val json = gson.toJson(items)
        context.libraryDataStore.edit { prefs ->
            prefs[KEY_LIBRARY_JSON] = json
        }
    }
}
