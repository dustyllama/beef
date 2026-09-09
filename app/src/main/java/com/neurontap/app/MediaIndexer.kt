package com.neurontap.app

import android.content.Context
import android.net.Uri
import androidx.documentfile.provider.DocumentFile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object MediaIndexer {
    suspend fun index(context: Context, db: NeuronDb, treeUri: Uri, onProgress: (Int) -> Unit = {}): Int = withContext(Dispatchers.IO) {
        val root = DocumentFile.fromTreeUri(context, treeUri) ?: return@withContext 0
        var count = 0
        db.runMediaBatch {
            fun walk(node: DocumentFile) {
                if (node.isDirectory) {
                    node.listFiles().forEach(::walk)
                    return
                }
                val mime = node.type ?: return
                if (!mime.startsWith("image/") && !mime.startsWith("video/")) return
                db.upsertMedia(treeUri.toString(), node.uri.toString(), node.name ?: "Untitled", mime, node.length(), node.lastModified())
                count++
                if (count % 100 == 0) onProgress(count)
            }
            walk(root)
        }
        onProgress(count)
        count
    }
}
