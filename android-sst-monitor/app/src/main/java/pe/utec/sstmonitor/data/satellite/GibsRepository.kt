package pe.utec.sstmonitor.data.satellite

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * Descarga fotogramas WMS de NASA GIBS como Bitmap. La cache en memoria por URL
 * cumple el rol de los objetos Image retenidos del visor web: alternar de capa o
 * volver a un encuadre reciente no re-descarga (el producto es diario, la misma
 * URL siempre devuelve la misma imagen dentro de la sesion).
 */
class GibsRepository {

    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(40, TimeUnit.SECONDS)
        .build()

    // ~64 MB: unas ~30 imagenes de 600x768 ARGB; LRU descarta las mas antiguas.
    private val cache = object : LruCache<String, Bitmap>(64 * 1024 * 1024) {
        override fun sizeOf(key: String, value: Bitmap): Int = value.byteCount
    }

    /** Devuelve el Bitmap de la URL o null (sin dato / error de red): fail-open. */
    suspend fun fetch(url: String): Bitmap? = withContext(Dispatchers.IO) {
        cache.get(url)?.let { return@withContext it }
        runCatching {
            val req = Request.Builder()
                .url(url)
                .header("User-Agent", "SSTMonitorPeru/1.0 (capstone UTEC; educativo)")
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@runCatching null
                val bytes = resp.body?.bytes() ?: return@runCatching null
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
            }
        }.getOrNull()?.also { cache.put(url, it) }
    }
}
