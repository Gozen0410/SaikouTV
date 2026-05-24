package ani.saikou.parsers.anime

import ani.saikou.FileUrl
import ani.saikou.Mapper
import ani.saikou.client
import ani.saikou.parsers.*
import ani.saikou.tryWithSuspend
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

import java.util.Base64
import java.util.zip.GZIPInputStream

class Miruro : AnimeParser() {

    companion object {
        private val PIPE_KEY = "71951034f8fbcf53d89db52ceb3dc22c"
            .chunked(2).map { it.toInt(16).toByte() }.toByteArray()
        private val PROVIDER_PRIORITY = listOf("kiwi", "ally", "dune", "bee", "hop")
    }

    override val hostUrl = "https://www.miruro.tv"
    override val name = "Miruro"
    override val saveName = "miruro_tv"
    override val isDubAvailableSeparately = false

    override suspend fun search(query: String): List<ShowResponse> = tryWithSuspend {
        val data = pipe("search", JsonObject(mapOf(
            "q" to JsonPrimitive(query),
            "limit" to JsonPrimitive(8),
            "offset" to JsonPrimitive(0),
            "type" to JsonPrimitive("ANIME"),
            "sort" to JsonPrimitive("POPULARITY_DESC")
        )))
        val arr = Mapper.json.decodeFromString<List<SearchAnime>>(data.decodeToString())
        arr.map { anime ->
            ShowResponse(
                name = anime.title.userPreferred,
                link = anime.id.toString(),
                coverUrl = anime.coverImage.large,
                otherNames = listOfNotNull(anime.title.english, anime.title.romaji)
                    .filter { it != anime.title.userPreferred },
                total = anime.episodes,
                extra = mapOf("id" to anime.id.toString())
            )
        }
    } ?: emptyList()

    override suspend fun loadEpisodes(animeLink: String, extra: Map<String, String>?): List<Episode> = tryWithSuspend {
        val id = extra?.get("id") ?: animeLink
        val data = pipe("episodes", JsonObject(mapOf("anilistId" to JsonPrimitive(id))))
        val parsed = Mapper.json.decodeFromString<EpisodesResponse>(data.decodeToString())

        val providerEntry = PROVIDER_PRIORITY.firstNotNullOfOrNull { name ->
            parsed.providers[name]?.takeIf { it.episodes.isNotEmpty() }
        } ?: return@tryWithSuspend emptyList()

        val cat = if (selectDub && "dub" in providerEntry.episodes) "dub" else "sub"
        val episodes = providerEntry.episodes[cat] ?: providerEntry.episodes.values.first()

        episodes.map { ep ->
            val epIds = mutableMapOf<String, String>("_cat" to cat)
            for ((provName, provData) in parsed.providers) {
                val provEps = provData.episodes[cat] ?: provData.episodes.values.firstOrNull() ?: continue
                val match = provEps.find { it.number == ep.number } ?: continue
                epIds[provName] = Base64.getDecoder().decode(match.id).decodeToString()
            }
            Episode(
                number = ep.number.toString(),
                link = id,
                title = ep.title,
                thumbnail = ep.image ?: "",
                description = ep.description,
                isFiller = ep.filler,
                extra = epIds.toMap()
            )
        }
    } ?: emptyList()

    @Suppress("UNCHECKED_CAST")
    override suspend fun loadVideoServers(episodeLink: String, extra: Any?): List<VideoServer> = tryWithSuspend {
        val anilistId = episodeLink
        val epIds = extra as? Map<String, String> ?: return@tryWithSuspend emptyList()
        val cat = epIds["_cat"] ?: "sub"

        PROVIDER_PRIORITY.mapNotNull { provider ->
            val plainEpId = epIds[provider] ?: return@mapNotNull null
            runCatching {
                val d = pipe("sources", JsonObject(mapOf(
                    "episodeId" to JsonPrimitive(plainEpId),
                    "provider" to JsonPrimitive(provider),
                    "category" to JsonPrimitive(cat),
                    "anilistId" to JsonPrimitive(anilistId.toInt())
                )))
                val sources = Mapper.json.decodeFromString<SourcesResponse>(d.decodeToString())
                sources.streams.filter { it.type == "hls" }.map { stream ->
                    val q = stream.quality?.substringBefore("p")?.toIntOrNull() ?: 0
                    val label = stream.quality ?: q.let { if (it > 0) "${it}p" else "Auto" }
                    VideoServer(
                        name = "Miruro [$provider] $label",
                        embedUrl = stream.url,
                        extraData = mapOf(
                            "url" to stream.url,
                            "quality" to q,
                            "referer" to (stream.referer ?: hostUrl),
                            "subs" to Mapper.json.encodeToString(sources.subtitles)
                        )
                    )
                }
            }.getOrNull()
        }.flatten()
    } ?: emptyList()

    override suspend fun getVideoExtractor(server: VideoServer): VideoExtractor =
        MiruroExtractor(server)

    class MiruroExtractor(override val server: VideoServer) : VideoExtractor() {
        @Suppress("UNCHECKED_CAST")
        override suspend fun extract(): VideoContainer {
            val data = (server.extraData as? Map<String, Any>) ?: return VideoContainer(emptyList())
            val url = data["url"] as? String ?: return VideoContainer(emptyList())
            val quality = data["quality"] as? Int ?: 0
            val referer = data["referer"] as? String ?: ""
            val subs = (data["subs"] as? String)?.let { subJson ->
                runCatching { Mapper.json.decodeFromString<List<SubtitleData>>(subJson) }.getOrNull()
            } ?: emptyList()
            return VideoContainer(
                videos = listOf(Video(quality, VideoType.M3U8, FileUrl(url, mapOf("referer" to referer)))),
                subtitles = subs.map { Subtitle(it.label ?: it.language ?: "Unknown", it.file, SubtitleType.VTT) }
            )
        }
    }

    private suspend fun pipe(path: String, query: JsonObject): ByteArray {
        val request = JsonObject(mapOf(
            "path" to JsonPrimitive(path),
            "method" to JsonPrimitive("GET"),
            "query" to query,
            "body" to JsonNull,
            "version" to JsonPrimitive("0.2.0")
        ))
        val e = Base64.getUrlEncoder().withoutPadding().encodeToString(
            Mapper.json.encodeToString(request).encodeToByteArray()
        )
        val respText = client.get("$hostUrl/api/secure/pipe?e=$e", mapOf("referer" to hostUrl)).text
        val decoded = try {
            Base64.getUrlDecoder().decode(respText)
        } catch (_: IllegalArgumentException) {
            return@pipe ByteArray(0)
        }
        val xored = ByteArray(decoded.size)
        for (i in decoded.indices) {
            val b = decoded[i].toInt() and 0xFF
            val k = PIPE_KEY[i % PIPE_KEY.size].toInt() and 0xFF
            xored[i] = (b xor k).toByte()
        }
        val bos = ByteArrayOutputStream()
        GZIPInputStream(ByteArrayInputStream(xored)).transferTo(bos)
        return bos.toByteArray()
    }

    @Serializable
    data class SearchAnime(
        val id: Int,
        val title: SearchTitle,
        val coverImage: CoverImage,
        val episodes: Int? = null
    )

    @Serializable
    data class SearchTitle(
        val native: String? = null,
        val romaji: String? = null,
        val english: String? = null,
        val userPreferred: String
    )

    @Serializable
    data class CoverImage(val large: String)

    @Serializable
    data class EpisodesResponse(
        val mappings: Mappings,
        val providers: Map<String, ProviderData>
    )

    @Serializable
    data class Mappings(val id: Int, val title: String? = null, val episodes: Int? = null)

    @Serializable
    data class ProviderData(
        val meta: ProviderMeta? = null,
        val episodes: Map<String, List<EpisodeData>>
    )

    @Serializable
    data class ProviderMeta(val totalEpisodes: Int? = null)

    @Serializable
    data class EpisodeData(
        val id: String,
        val number: Int,
        val title: String? = null,
        val image: String? = null,
        val description: String? = null,
        val filler: Boolean = false
    )

    @Serializable
    data class SourcesResponse(
        val streams: List<StreamData>,
        val subtitles: List<SubtitleData> = emptyList(),
        val download: String? = null
    )

    @Serializable
    data class StreamData(
        val url: String,
        val type: String,
        val quality: String? = null,
        val referer: String? = null,
        val audio: String? = null,
        val isActive: Boolean = false
    )

    @Serializable
    data class SubtitleData(
        val file: String,
        val label: String? = null,
        val language: String? = null,
        val kind: String? = null,
        val format: String? = null
    )
}
