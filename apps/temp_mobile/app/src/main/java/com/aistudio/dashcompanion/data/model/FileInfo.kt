package com.aistudio.dashcompanion.data.model

import com.squareup.moshi.Json

data class FileInfo(
    @Json(name = "name") val name: String = "",
    @Json(name = "type") val type: FileType = FileType.FILE,
    @Json(name = "size") val size: Long = 0,
    @Json(name = "modified") val modified: String = "",
    @Json(name = "path") val path: String = ""
)

enum class FileType {
    @Json(name = "file") FILE,
    @Json(name = "directory") DIRECTORY
}

data class BrowseResponse(
    @Json(name = "path") val path: String = "",
    @Json(name = "entries") val entries: List<FileInfo> = emptyList(),
    @Json(name = "count") val count: Int = 0
)

data class FileOperationRequest(
    @Json(name = "source") val source: String = "",
    @Json(name = "destination") val destination: String = "",
    @Json(name = "path") val path: String = "",
    @Json(name = "new_name") val newName: String = "",
    @Json(name = "permanent") val permanent: Boolean = false
)

data class FileOperationResponse(
    @Json(name = "status") val status: String = "ok",
    @Json(name = "summary") val summary: String = "",
    @Json(name = "details") val details: Map<String, Any> = emptyMap()
)
