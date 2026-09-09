package com.neurontap.app

import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class AlbumGroup(val id: String, var name: String, val roots: MutableList<String>)

data class AlbumLayoutState(
    val order: MutableList<String> = mutableListOf(),
    val groups: MutableMap<String, AlbumGroup> = linkedMapOf()
) {
    fun topLevelAlbums(): Set<String> = order.filter { it.startsWith("a:") }.map { it.removePrefix("a:") }.toSet()
    fun groupedAlbums(): Set<String> = groups.values.flatMap { it.roots }.toSet()
}

object AlbumOrganizer {
    private const val PREF_KEY = "album_layout_v1"

    fun load(prefs: SharedPreferences, actualRoots: Set<String>): AlbumLayoutState {
        val state = runCatching { decode(prefs.getString(PREF_KEY, null)) }.getOrElse { AlbumLayoutState() }

        // Remove albums that no longer exist, but preserve group names/order when possible.
        state.groups.values.forEach { it.roots.retainAll(actualRoots) }
        state.groups.entries.removeAll { it.value.roots.isEmpty() }
        state.order.removeAll { token ->
            when {
                token.startsWith("a:") -> token.removePrefix("a:") !in actualRoots
                token.startsWith("g:") -> token.removePrefix("g:") !in state.groups
                else -> true
            }
        }

        val represented = state.topLevelAlbums() + state.groupedAlbums()
        actualRoots.filter { it !in represented }.sortedBy(::albumLabel).forEach { state.order += "a:$it" }
        save(prefs, state)
        return state
    }

    fun save(prefs: SharedPreferences, state: AlbumLayoutState) {
        prefs.edit().putString(PREF_KEY, encode(state)).apply()
    }

    fun createGroup(prefs: SharedPreferences, state: AlbumLayoutState, a: String, b: String): String {
        if (a == b) return ""
        removeAlbumEverywhere(state, a)
        removeAlbumEverywhere(state, b)
        val id = UUID.randomUUID().toString().take(8)
        val group = AlbumGroup(id, "New group", mutableListOf(a, b))
        state.groups[id] = group
        state.order += "g:$id"
        save(prefs, state)
        return id
    }

    fun addToGroup(prefs: SharedPreferences, state: AlbumLayoutState, root: String, groupId: String) {
        val group = state.groups[groupId] ?: return
        removeAlbumEverywhere(state, root)
        if (root !in group.roots) group.roots += root
        if ("g:$groupId" !in state.order) state.order += "g:$groupId"
        save(prefs, state)
    }

    fun reorderTop(prefs: SharedPreferences, state: AlbumLayoutState, sourceToken: String, targetToken: String, before: Boolean) {
        if (sourceToken == targetToken) return
        val sourceIndex = state.order.indexOf(sourceToken)
        val targetIndex = state.order.indexOf(targetToken)
        if (sourceIndex < 0 || targetIndex < 0) return
        state.order.removeAt(sourceIndex)
        var newTarget = state.order.indexOf(targetToken)
        if (!before) newTarget++
        state.order.add(newTarget.coerceIn(0, state.order.size), sourceToken)
        save(prefs, state)
    }

    fun reorderInsideGroup(prefs: SharedPreferences, state: AlbumLayoutState, groupId: String, sourceRoot: String, targetRoot: String) {
        val roots = state.groups[groupId]?.roots ?: return
        val source = roots.indexOf(sourceRoot); val target = roots.indexOf(targetRoot)
        if (source < 0 || target < 0 || source == target) return
        roots.removeAt(source)
        roots.add(roots.indexOf(targetRoot).coerceAtLeast(0), sourceRoot)
        save(prefs, state)
    }

    fun renameGroup(prefs: SharedPreferences, state: AlbumLayoutState, groupId: String, name: String) {
        val group = state.groups[groupId] ?: return
        group.name = name.trim().ifBlank { "Group" }
        save(prefs, state)
    }

    fun ungroup(prefs: SharedPreferences, state: AlbumLayoutState, groupId: String) {
        val group = state.groups.remove(groupId) ?: return
        val token = "g:$groupId"
        val index = state.order.indexOf(token).let { if (it < 0) state.order.size else it }
        state.order.remove(token)
        group.roots.forEachIndexed { offset, root -> state.order.add((index + offset).coerceAtMost(state.order.size), "a:$root") }
        save(prefs, state)
    }

    fun removeFromGroup(prefs: SharedPreferences, state: AlbumLayoutState, groupId: String, root: String) {
        val group = state.groups[groupId] ?: return
        group.roots.remove(root)
        val groupTokenIndex = state.order.indexOf("g:$groupId").coerceAtLeast(0)
        state.order.add((groupTokenIndex + 1).coerceAtMost(state.order.size), "a:$root")
        if (group.roots.size <= 1) {
            val leftovers = group.roots.toList()
            state.groups.remove(groupId)
            state.order.remove("g:$groupId")
            leftovers.forEach { if ("a:$it" !in state.order) state.order.add(groupTokenIndex.coerceAtMost(state.order.size), "a:$it") }
        }
        save(prefs, state)
    }

    private fun removeAlbumEverywhere(state: AlbumLayoutState, root: String) {
        state.order.remove("a:$root")
        state.groups.values.forEach { it.roots.remove(root) }
        val empty = state.groups.filterValues { it.roots.isEmpty() }.keys
        empty.forEach { state.groups.remove(it); state.order.remove("g:$it") }
    }

    private fun encode(state: AlbumLayoutState): String {
        val obj = JSONObject()
        obj.put("order", JSONArray(state.order))
        val groups = JSONArray()
        state.groups.values.forEach { group ->
            groups.put(JSONObject().apply {
                put("id", group.id); put("name", group.name); put("roots", JSONArray(group.roots))
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
            val rootsJson = g.optJSONArray("roots") ?: JSONArray()
            val roots = MutableList(rootsJson.length()) { j -> rootsJson.getString(j) }
            val group = AlbumGroup(g.getString("id"), g.optString("name", "Group"), roots)
            groups[group.id] = group
        }
        return AlbumLayoutState(order, groups)
    }
}
