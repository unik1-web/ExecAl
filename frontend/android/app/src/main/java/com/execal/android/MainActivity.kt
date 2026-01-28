package com.execal.android

import android.content.ContentResolver
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private val picker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@registerForActivityResult
        contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        onPicked?.invoke(uri, contentResolver)
    }

    private var onPicked: ((Uri, ContentResolver) -> Unit)? = null

    private val savePdfPicker =
        registerForActivityResult(ActivityResultContracts.CreateDocument("application/pdf")) { uri: Uri? ->
            if (uri == null) return@registerForActivityResult
            val bytes = pendingPdfBytes ?: return@registerForActivityResult
            pendingPdfBytes = null
            runCatching {
                contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
                    ?: error("Не удалось открыть OutputStream")
            }
        }

    private var pendingPdfBytes: ByteArray? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            MaterialTheme {
                var apiBase by remember { mutableStateOf(BuildConfig.API_BASE) }
                var email by remember { mutableStateOf("user+${System.currentTimeMillis()}@example.com") }
                var password by remember { mutableStateOf("password123") }
                var token by remember { mutableStateOf("") }
                var status by remember { mutableStateOf("") }
                var lastAnalysisId by remember { mutableStateOf<Int?>(null) }
                var lastReportJson by remember { mutableStateOf<String?>(null) }

                val api = remember(apiBase) { ExecAlApi(apiBase) }

                fun pickDocument(cb: (Uri, ContentResolver) -> Unit) {
                    onPicked = cb
                    picker.launch(arrayOf("application/pdf", "image/*"))
                }

                Column(
                    modifier = Modifier.fillMaxSize().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text("ExecAl Android (MVP)", style = MaterialTheme.typography.headlineSmall)

                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(
                                value = apiBase,
                                onValueChange = { apiBase = it.trim() },
                                label = { Text("API base") },
                                modifier = Modifier.fillMaxWidth()
                            )
                            Text("Для эмулятора: http://10.0.2.2:8000 (Docker backend на хосте).")
                        }
                    }

                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(
                                value = email,
                                onValueChange = { email = it },
                                label = { Text("Email") },
                                modifier = Modifier.fillMaxWidth()
                            )
                            OutlinedTextField(
                                value = password,
                                onValueChange = { password = it },
                                label = { Text("Password") },
                                modifier = Modifier.fillMaxWidth()
                            )
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(onClick = {
                                    lifecycleScope.launch {
                                        status = "Регистрация..."
                                        runCatching {
                                            api.register(email, password)
                                        }.onSuccess {
                                            status = "Register OK"
                                        }.onFailure {
                                            status = "ERROR: ${it.message}"
                                        }
                                    }
                                }) { Text("Register") }
                                Button(onClick = {
                                    lifecycleScope.launch {
                                        status = "Вход..."
                                        runCatching {
                                            val t = api.login(email, password)
                                            token = t
                                            status = "Login OK"
                                        }.onFailure {
                                            token = ""
                                            status = "ERROR: ${it.message}"
                                        }
                                    }
                                }) { Text("Login") }
                            }
                            Text("Token: ${if (token.isNotBlank()) "OK" else "—"}")
                        }
                    }

                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = {
                                pickDocument { uri, cr ->
                                    lifecycleScope.launch {
                                        status = "Читаю файл..."
                                        lastReportJson = null
                                        lastAnalysisId = null
                                        runCatching {
                                            val bytes = cr.openInputStream(uri)?.use { it.readBytes() }
                                                ?: error("Не удалось прочитать файл")
                                            val name = uri.lastPathSegment ?: "document"
                                            val contentType = cr.getType(uri)
                                            status = "Загрузка..."
                                            val analysisId = api.upload(token, name, contentType, bytes)
                                            lastAnalysisId = analysisId
                                            status = "Получаю отчёт..."
                                            val report = api.getReport(token, analysisId)
                                            lastReportJson = report
                                            status = "Готово. analysis_id=$analysisId"
                                        }.onFailure {
                                            status = "ERROR: ${it.message}"
                                        }
                                    }
                                }
                            }) { Text("Upload document") }

                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(
                                    enabled = lastAnalysisId != null,
                                    onClick = {
                                        val id = lastAnalysisId ?: return@Button
                                        lifecycleScope.launch {
                                            status = "Обновляю отчёт..."
                                            runCatching {
                                                lastReportJson = api.getReport(token, id)
                                                status = "Ок"
                                            }.onFailure { status = "ERROR: ${it.message}" }
                                        }
                                    }
                                ) { Text("Refresh report") }
                                Button(
                                    enabled = lastAnalysisId != null,
                                    onClick = {
                                        val id = lastAnalysisId ?: return@Button
                                        lifecycleScope.launch {
                                            status = "Скачиваю PDF..."
                                            runCatching {
                                                val pdfBytes = api.getReportPdf(token, id)
                                                pendingPdfBytes = pdfBytes
                                                savePdfPicker.launch("report_$id.pdf")
                                                status = "Выберите место сохранения PDF..."
                                            }.onFailure { status = "ERROR: ${it.message}" }
                                        }
                                    }
                                ) { Text("Download PDF") }
                            }
                        }
                    }

                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("Status")
                            SelectionContainer {
                                Text(status)
                            }
                            Spacer(Modifier.height(8.dp))
                            Text("Report JSON")
                            SelectionContainer {
                                Text(lastReportJson ?: "—")
                            }
                        }
                    }
                }
            }
        }
    }
}


