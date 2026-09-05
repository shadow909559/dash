package com.aistudio.dashcompanion.data.datastore

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.aistudio.dashcompanion.data.config.AppConfig
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

class SettingsDataStore(private val context: Context) {
    private object PreferencesKeys {
        val SERVER_IP = stringPreferencesKey("server_ip")
        val SERVER_PORT = stringPreferencesKey("server_port")
        val ACCESS_TOKEN = stringPreferencesKey("access_token")
        val REFRESH_TOKEN = stringPreferencesKey("refresh_token")
        val IS_LOGGED_IN = booleanPreferencesKey("is_logged_in")
        val DARK_THEME = booleanPreferencesKey("dark_theme")
        val AUTO_RECONNECT = booleanPreferencesKey("auto_reconnect")
        val VOICE_ENABLED = booleanPreferencesKey("voice_enabled")
        val NOTIFICATIONS_ENABLED = booleanPreferencesKey("notifications_enabled")
    }

    val serverIp: Flow<String> = context.dataStore.data
        .map { preferences ->
            preferences[PreferencesKeys.SERVER_IP] ?: AppConfig.SERVER_IP
        }

    val serverPort: Flow<String> = context.dataStore.data
        .map { preferences ->
            preferences[PreferencesKeys.SERVER_PORT] ?: AppConfig.SERVER_PORT
        }

    val accessToken: Flow<String?> = context.dataStore.data
        .map { preferences ->
            preferences[PreferencesKeys.ACCESS_TOKEN]
        }

    val refreshToken: Flow<String?> = context.dataStore.data
        .map { preferences ->
            preferences[PreferencesKeys.REFRESH_TOKEN]
        }

    val isLoggedIn: Flow<Boolean> = context.dataStore.data
        .map { preferences ->
            preferences[PreferencesKeys.IS_LOGGED_IN] ?: false
        }

    val darkTheme: Flow<Boolean> = context.dataStore.data
        .map { preferences ->
            preferences[PreferencesKeys.DARK_THEME] ?: true
        }

    val autoReconnect: Flow<Boolean> = context.dataStore.data
        .map { preferences ->
            preferences[PreferencesKeys.AUTO_RECONNECT] ?: true
        }

    val voiceEnabled: Flow<Boolean> = context.dataStore.data
        .map { preferences ->
            preferences[PreferencesKeys.VOICE_ENABLED] ?: true
        }

    val notificationsEnabled: Flow<Boolean> = context.dataStore.data
        .map { preferences ->
            preferences[PreferencesKeys.NOTIFICATIONS_ENABLED] ?: true
        }

    suspend fun setServerIp(ip: String) {
        context.dataStore.edit { preferences ->
            preferences[PreferencesKeys.SERVER_IP] = ip
        }
    }

    suspend fun setServerPort(port: String) {
        context.dataStore.edit { preferences ->
            preferences[PreferencesKeys.SERVER_PORT] = port
        }
    }

    suspend fun setAccessToken(token: String?) {
        context.dataStore.edit { preferences ->
            if (token != null) {
                preferences[PreferencesKeys.ACCESS_TOKEN] = token
            } else {
                preferences.remove(PreferencesKeys.ACCESS_TOKEN)
            }
        }
    }

    suspend fun setRefreshToken(token: String?) {
        context.dataStore.edit { preferences ->
            if (token != null) {
                preferences[PreferencesKeys.REFRESH_TOKEN] = token
            } else {
                preferences.remove(PreferencesKeys.REFRESH_TOKEN)
            }
        }
    }

    suspend fun setLoggedIn(loggedIn: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[PreferencesKeys.IS_LOGGED_IN] = loggedIn
        }
    }

    suspend fun setDarkTheme(enabled: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[PreferencesKeys.DARK_THEME] = enabled
        }
    }

    suspend fun setAutoReconnect(enabled: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[PreferencesKeys.AUTO_RECONNECT] = enabled
        }
    }

    suspend fun setVoiceEnabled(enabled: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[PreferencesKeys.VOICE_ENABLED] = enabled
        }
    }

    suspend fun setNotificationsEnabled(enabled: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[PreferencesKeys.NOTIFICATIONS_ENABLED] = enabled
        }
    }

    suspend fun clearAll() {
        context.dataStore.edit { preferences ->
            preferences.clear()
        }
    }
}
