package pe.utec.sstmonitor.data

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Query
import java.util.concurrent.TimeUnit

/** Cliente Retrofit de la API Marine de Open-Meteo (gratuita, sin API key). */
interface MarineApi {

    @GET("v1/marine")
    suspend fun getSst(
        @Query("latitude") latitude: Double,
        @Query("longitude") longitude: Double,
        @Query("hourly") hourly: String = "sea_surface_temperature",
        @Query("past_days") pastDays: Int = 7,
        @Query("forecast_days") forecastDays: Int = 3,
        @Query("timezone") timezone: String = "America/Lima",
    ): MarineResponse

    companion object {
        private const val BASE_URL = "https://marine-api.open-meteo.com/"

        fun create(): MarineApi {
            val logging = HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BASIC
            }
            val client = OkHttpClient.Builder()
                .addInterceptor(logging)
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(20, TimeUnit.SECONDS)
                .build()

            return Retrofit.Builder()
                .baseUrl(BASE_URL)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(MarineApi::class.java)
        }
    }
}
