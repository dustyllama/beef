from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/AlbumOrganizer.kt"
p.write_text(r'''package com.neurontap.app

import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class AlbumGroup(val id: String, var name: String, val children: MutableList<String>)

data class AlbumLayoutState(
    val order: MutableList<String> = mutableListOf(),
    val groups: MutableMap<String, AlbumGroup> = linkedMapOf()
) {
    fun childrenOf(groupId: String): List<String> = groups[groupId]?.children.orEmpty()

    fun rootsForGroup(groupId: String): List<String> {
        val out = linkedSetOf<String>()
        val seen = mutableSetOf<String>()
        fun walk(id: String) {
            if (!seen.add(id)) return
            groups[id]?.children.orEmpty().forEach { token ->
                when {
                    token.startsWith("a:") -> out += token.removePrefix("a:")
                    token.startsWith("g:") -> walk(token.removePrefix("g:"))
                }
            }
        }
        walk(groupId)
        return out.toList()
    }

    fun representedAlbums(): Set<String> {
        val out = linkedSetOf<String>()
        order.forEach { token ->
            when {
                token.startsWith("a:") -> out += token.removePrefix("a:")
                token.startsWith("g:") -> out += rootsForGroup(token.removePrefix("g:"))
            }
        }
        return out
    }
}

object AlbumOrganizer {
    private const val PREF_KEY = "album_layout_v1"

    fun load(prefs: SharedPreferences, actualRoots: Set<String>): AlbumLayoutState {
        val state = runCatching { decode(prefs.getString(PREF_KEY, null)) }.getOrElse { AlbumLayoutState() }
        sanitize(state, actualRoots)
        val represented = state.representedAlbums()
        actualRoots.filter { it !in represented }.sortedBy(::albumLabel).forEach { state.order += "a:$it" }
        save(prefs, state)
        return state
    }

    fun save(prefs: SharedPreferences, state: AlbumLayoutState) {
        prefs.edit().putString(PREF_KEY, encode(state)).apply()
    }

    fun createGroup(prefs: SharedPreferences, state: AlbumLayoutState, a: String, b: String): String =
        createCollectionFromTokens(prefs, state, null, "a:$a", "a:$b")

    fun addToGroup(prefs: SharedPreferences, state: AlbumLayoutState, root: String, groupId: String) {
        addTokenToGroup(prefs, state, "a:$root", groupId, findParent(state, "a:$root"))
    }

    fun reorderTop(prefs: SharedPreferences, state: AlbumLayoutState, sourceToken: String, targetToken: String, before: Boolean) =
        reorderInContainer(prefs, state, null, sourceToken, targetToken, before)

    fun reorderInsideGroup(prefs: SharedPreferences, state: AlbumLayoutState, groupId: String, sourceRoot: String, targetRoot: String) =
        reorderInContainer(prefs, state, groupId, "a:$sourceRoot", "a:$targetRoot", true)

    fun renameGroup(prefs: SharedPreferences, state: AlbumLayoutState, groupId: String, name: String) {
        state.groups[groupId]?.name = name.trim().ifBlank { "Collection" }
        save(prefs, state)
    }

    fun createCollectionFromTokens(
        prefs: SharedPreferences,
        state: AlbumLayoutState,
        parentId: String?,
        sourceToken: String,
        targetToken: String
    ): String {
        if (sourceToken == targetToken) return ""
        val container = container(state, parentId) ?: return ""
        val a = container.indexOf(sourceToken)
        val b = container.indexOf(targetToken)
        if (a < 0 || b < 0) return ""
        val insertAt = minOf(a, b)
        container.remove(sourceToken); container.remove(targetToken)
        val id = UUID.randomUUID().toString().take(8)
        state.groups[id] = AlbumGroup(id, "Collection ${state.groups.size + 1}", mutableListOf(sourceToken, targetToken))
        container.add(insertAt.coerceIn(0, container.size), "g:$id")
        save(prefs, state)
        return id
    }

    fun addTokenToGroup(
        prefs: SharedPreferences,
        state: AlbumLayoutState,
        sourceToken: String,
        targetGroupId: String,
        sourceParentId: String?
    ): Boolean {
        val target = state.groups[targetGroupId] ?: return false
        if (sourceToken == "g:$targetGroupId") return false
        if (sourceToken.startsWith("g:")) {
            val movingId = sourceToken.removePrefix("g:")
            if (containsGroup(state, movingId, targetGroupId)) return false
        }
        val sourceContainer = container(state, sourceParentId) ?: return false
        if (!sourceContainer.remove(sourceToken)) return false
        if (sourceToken !in target.children) target.children += sourceToken
        save(prefs, state)
        return true
    }

    fun reorderInContainer(
        prefs: SharedPreferences,
        state: AlbumLayoutState,
        parentId: String?,
        sourceToken: String,
        targetToken: String,
        before: Boolean
    ) {
        if (sourceToken == targetToken) return
        val list = container(state, parentId) ?: return
        if (sourceToken !in list || targetToken !in list) return
        list.remove(sourceToken)
        var target = list.indexOf(targetToken)
        if (target < 0) return
        if (!before) target++
        list.add(target.coerceIn(0, list.size), sourceToken)
        save(prefs, state)
    }

    fun ungroup(prefs: SharedPreferences, state: AlbumLayoutState, groupId: String) {
        val group = state.groups[groupId] ?: return
        val token = "g:$groupId"
        val parent = findParent(state, token)
        val list = container(state, parent) ?: return
        val index = list.indexOf(token).let { if (it < 0) list.size else it }
        list.remove(token)
        state.groups.remove(groupId)
        group.children.forEachIndexed { offset, child -> list.add((index + offset).coerceAtMost(list.size), child) }
        save(prefs, state)
    }

    fun removeFromGroup(prefs: SharedPreferences, state: AlbumLayoutState, groupId: String, root: String) =
        removeTokenFromGroup(prefs, state, groupId, "a:$root")

    fun removeTokenFromGroup(prefs: SharedPreferences, state: AlbumLayoutState, groupId: String, token: String) {
        val group = state.groups[groupId] ?: return
        if (!group.children.remove(token)) return
        val parent = findParent(state, "g:$groupId")
        val parentList = container(state, parent) ?: state.order
        val groupIndex = parentList.indexOf("g:$groupId").let { if (it < 0) parentList.size else it }
        parentList.add((groupIndex + 1).coerceAtMost(parentList.size), token)
        collapseIfNeeded(state, groupId)
        save(prefs, state)
    }

    fun findParent(state: AlbumLayoutState, token: String): String? {
        if (token in state.order) return null
        return state.groups.values.firstOrNull { token in it.children }?.id
    }

    private fun container(state: AlbumLayoutState, parentId: String?): MutableList<String>? =
        if (parentId == null) state.order else state.groups[parentId]?.children

    private fun containsGroup(state: AlbumLayoutState, rootId: String, targetId: String): Boolean {
        if (rootId == targetId) return true
        val seen = mutableSetOf<String>()
        fun walk(id: String): Boolean {
            if (!seen.add(id)) return false
            return state.groups[id]?.children.orEmpty().any { token ->
                token.startsWith("g:") && (token.removePrefix("g:") == targetId || walk(token.removePrefix("g:")))
            }
        }
        return walk(rootId)
    }

    private fun collapseIfNeeded(state: AlbumLayoutState, groupId: String) {
        val group = state.groups[groupId] ?: return
        if (group.children.size > 1) return
        val token = "g:$groupId"
        val parent = findParent(state, token)
        val list = container(state, parent) ?: return
        val at = list.indexOf(token).let { if (it < 0) list.size else it }
        list.remove(token)
        state.groups.remove(groupId)
        group.children.firstOrNull()?.let { list.add(at.coerceAtMost(list.size), it) }
    }

    private fun sanitize(state: AlbumLayoutState, actualRoots: Set<String>) {
        // Drop impossible tokens and duplicate placements, preserve user order.
        val seenTokens = mutableSetOf<String>()
        fun cleanList(list: MutableList<String>, ancestry: Set<String>) {
            val cleaned = mutableListOf<String>()
            list.forEach { token ->
                when {
                    token.startsWith("a:") -> {
                        val root = token.removePrefix("a:")
                        if (root in actualRoots && seenTokens.add(token)) cleaned += token
                    }
                    token.startsWith("g:") -> {
                        val id = token.removePrefix("g:")
                        if (id in state.groups && id !in ancestry && seenTokens.add(token)) {
                            cleanList(state.groups[id]!!.children, ancestry + id)
                            if (state.groups[id]!!.children.isNotEmpty()) cleaned += token
                        }
                    }
                }
            }
            list.clear(); list.addAll(cleaned)
        }
        cleanList(state.order, emptySet())
        val reachable = mutableSetOf<String>()
        fun mark(id: String) {
            if (!reachable.add(id)) return
            state.groups[id]?.children.orEmpty().filter { it.startsWith("g:") }.forEach { mark(it.removePrefix("g:")) }
        }
        state.order.filter { it.startsWith("g:") }.forEach { mark(it.removePrefix("g:")) }
        state.groups.keys.retainAll(reachable)
    }

    private fun encode(state: AlbumLayoutState): String {
        val obj = JSONObject().put("version", 2).put("order", JSONArray(state.order))
        val groups = JSONArray()
        state.groups.values.forEach { group ->
            groups.put(JSONObject().apply {
                put("id", group.id); put("name", group.name); put("children", JSONArray(group.children))
            })
        }
        obj.put("groups", groups)
        return obj.toString()
    }

    private fun decode(raw: String?): AlbumLayoutState {
        if (raw.isNullOrBlank()) return AlbumLayoutState()
        val obj = JSONObject(raw)
        val orderJson = obj.optJSONArray("order") ?: JSONArray()
        val order = MutableList(orderJson.length()) { i -> orderJson.getString(i) }
        val groups = linkedMapOf<String, AlbumGroup>()
        val groupsJson = obj.optJSONArray("groups") ?: JSONArray()
        for (i in 0 until groupsJson.length()) {
            val g = groupsJson.getJSONObject(i)
            val id = g.getString("id")
            val childrenJson = g.optJSONArray("children")
            val children = if (childrenJson != null) {
                MutableList(childrenJson.length()) { j -> childrenJson.getString(j) }
            } else {
                // v1 migration: old collections only stored album roots.
                val roots = g.optJSONArray("roots") ?: JSONArray()
                MutableList(roots.length()) { j -> "a:${roots.getString(j)}" }
            }
            groups[id] = AlbumGroup(id, g.optString("name", "Collection"), children)
        }
        return AlbumLayoutState(order, groups)
    }
}
''')
print('Applied v7 nested collection organizer')
