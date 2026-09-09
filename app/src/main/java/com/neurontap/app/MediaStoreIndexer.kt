package com.neurontap.app

import android.content.ContentUris
import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

object MediaStoreIndexer {
    suspend fun index(context: Context, db: NeuronDb): Int = withContext(Dispatchers.IO) {
        var count = 0
        db.runMediaBatch {
            count += runCatching { indexCollection(context, db, MediaStore.Images.Media.EXTERNAL_CONTENT_URI) }.getOrDefault(0)
            count += runCatching { indexCollection(context, db, MediaStore.Video.Media.EXTERNAL_CONTENT_URI) }.getOrDefault(0)
        }
        count
    }

    private fun indexCollection(context: Context, db: NeuronDb, collection: Uri): Int {
        val modern = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
        val projection = if (modern) {
            arrayOf(
                MediaStore.MediaColumns._ID,
                MediaStore.MediaColumns.DISPLAY_NAME,
                MediaStore.MediaColumns.MIME_TYPE,
                MediaStore.MediaColumns.SIZE,
                MediaStore.MediaColumns.DATE_MODIFIED,
                MediaStore.MediaColumns.RELATIVE_PATH
            )
        } else {
            arrayOf(
                MediaStore.MediaColumns._ID,
                MediaStore.MediaColumns.DISPLAY_NAME,
                MediaStore.MediaColumns.MIME_TYPE,
                MediaStore.MediaColumns.SIZE,
                MediaStore.MediaColumns.DATE_MODIFIED,
                MediaStore.MediaColumns.DATA
            )
        }

        var count = 0
        context.contentResolver.query(collection, projection, null, null, "${MediaStore.MediaColumns.DATE_MODIFIED} DESC")?.use { cursor ->
            val idCol = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns._ID)
            val nameCol = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns.DISPLAY_NAME)
            val mimeCol = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns.MIME_TYPE)
            val sizeCol = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns.SIZE)
            val modifiedCol = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns.DATE_MODIFIED)
            val pathCol = cursor.getColumnIndexOrThrow(if (modern) MediaStore.MediaColumns.RELATIVE_PATH else MediaStore.MediaColumns.DATA)
            while (cursor.moveToNext()) {
                val id = cursor.getLong(idCol)
                val name = cursor.getString(nameCol) ?: "Untitled"
                val mime = cursor.getString(mimeCol) ?: continue
                val size = cursor.getLong(sizeCol)
                val modified = cursor.getLong(modifiedCol) * 1000L
                val pathValue = cursor.getString(pathCol).orEmpty()
                val albumPath = if (modern) pathValue.trim('/').ifBlank { "Device" } else File(pathValue).parent ?: "Device"
                val uri = ContentUris.withAppendedId(collection, id)
                db.upsertMedia("mediastore:$albumPath", uri.toString(), name, mime, size, modified)
                count++
            }
        }
        return count
    }
}
