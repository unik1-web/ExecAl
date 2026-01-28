package com.execal.android

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.okhttp.OkHttp
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.request.forms.formData
import io.ktor.client.request.forms.submitFormWithBinaryData
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.Headers
import io.ktor.http.HttpHeaders
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

class ExecAlApi(private val baseUrl: String) {
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }
    private val jsonPretty = Json {
        ignoreUnknownKeys = true
        isLenient = true
        prettyPrint = true
    }

    private val client = HttpClient(OkHttp) {
        install(ContentNegotiation) {
            json(json)
        }
    }

    @Serializable
    private data class AuthReq(val email: String, val password: String)

    @Serializable
    private data class LoginResp(@SerialName("access_token") val accessToken: String)

    @Serializable
    private data class UploadResp(@SerialName("analysis_id") val analysisId: Int? = null, val analysisIdAlt: Int? = null)

    suspend fun register(email: String, password: String) {
        client.post("$baseUrl/auth/register") {
            contentType(ContentType.Application.Json)
            setBody(AuthReq(email, password))
        }
    }

    suspend fun login(email: String, password: String): String {
        val resp = client.post("$baseUrl/auth/login") {
            contentType(ContentType.Application.Json)
            setBody(AuthReq(email, password))
        }.body<LoginResp>()
        return resp.accessToken
    }

    suspend fun upload(token: String, fileName: String, contentType: String?, bytes: ByteArray): Int {
        val resp = client.submitFormWithBinaryData(
            url = "$baseUrl/upload/document",
            formData = formData {
                append(
                    key = "file",
                    value = bytes,
                    headers = Headers.build {
                        append(
                            HttpHeaders.ContentDisposition,
                            "form-data; name=\"file\"; filename=\"$fileName\""
                        )
                        append(HttpHeaders.ContentType, contentType ?: "application/octet-stream")
                    }
                )
            }
        ) {
            if (token.isNotBlank()) header(HttpHeaders.Authorization, "Bearer $token")
        }.body<kotlinx.serialization.json.JsonObject>()

        val id = resp["analysis_id"]?.toString()?.trim('"') ?: resp["analysisId"]?.toString()?.trim('"')
        return id?.toIntOrNull() ?: error("Backend не вернул analysis_id: $resp")
    }

    suspend fun getReport(token: String, analysisId: Int): String {
        val txt = client.get("$baseUrl/report/$analysisId") {
            if (token.isNotBlank()) header(HttpHeaders.Authorization, "Bearer $token")
        }.bodyAsText()
        // pretty-print если это JSON
        return runCatching {
            val el = jsonPretty.parseToJsonElement(txt)
            jsonPretty.encodeToString(kotlinx.serialization.json.JsonElement.serializer(), el)
        }.getOrElse { txt }
    }

    suspend fun getReportPdf(token: String, analysisId: Int): ByteArray {
        return client.get("$baseUrl/report/$analysisId/pdf") {
            if (token.isNotBlank()) header(HttpHeaders.Authorization, "Bearer $token")
        }.body<ByteArray>()
    }
}

