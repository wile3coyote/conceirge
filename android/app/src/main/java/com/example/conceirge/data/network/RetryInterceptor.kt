package com.example.conceirge.data.network

import okhttp3.Interceptor
import okhttp3.Response
import java.io.IOException

/**
 * Application-level OkHttp interceptor that retries requests which fail with an
 * [IOException] (connect timeout, read timeout, socket reset, etc.).
 *
 * HTTP 4xx / 5xx responses are passed through unchanged — only transport-layer
 * failures are retried, so the UI never accidentally re-submits a bad request.
 *
 * Backoff delays apply between attempts (index 0 = delay before attempt 2, etc.).
 * [Thread.sleep] is intentional: OkHttp dispatches interceptors on a worker thread.
 *
 * @param maxAttempts Total number of attempts (1 original + up to maxAttempts-1 retries).
 * @param backoffMs   Milliseconds to wait before each successive retry.
 */
class RetryInterceptor(
    private val maxAttempts: Int = 3,
    private val backoffMs: List<Long> = listOf(500L, 1500L, 4500L),
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        var attempt = 0
        var lastError: IOException? = null

        while (attempt < maxAttempts) {
            try {
                return chain.proceed(chain.request())
            } catch (e: IOException) {
                lastError = e
                attempt++
                if (attempt >= maxAttempts) break
                Thread.sleep(backoffMs[attempt - 1])
            }
        }

        throw lastError ?: IOException("RetryInterceptor exhausted without error")
    }
}
