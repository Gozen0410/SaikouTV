package ani.saikou.parsers.anime

import ani.saikou.FileUrl
import ani.saikou.client
import ani.saikou.parsers.*
import ani.saikou.tryWithSuspend
import org.jsoup.nodes.Element

class AniDb : AnimeParser() {

    override val hostUrl = "https://anidb.app"
    override val name = "AniDb"
    override val saveName = "anidb_app"
    override val isDubAvailableSeparately = false

    /**
     * Search: GET /search/suggestions?q={query}
     * Returns HTML fragments with data-search-item elements.
     * Each item has:
     *   - href="/anime/{slug}-{id}"
     *   - an <img> for poster
     *   - the anime title text
     */
    override suspend fun search(query: String): List<ShowResponse> = tryWithSuspend {
        val doc = client.get(
            "$hostUrl/search/suggestions?q=${encode(query)}",
            mapOf("referer" to hostUrl, "X-Requested-With" to "XMLHttpRequest")
        ).document

        doc.select("[data-search-item]").map { el ->
            val link = el.attr("href").trim()
            val title = el.ownText().ifEmpty { el.text() }
            val img = el.selectFirst("img")
            val posterUrl = img?.attr("src") ?: ""

            ShowResponse(
                name = title,
                link = link,
                coverUrl = FileUrl(posterUrl),
                // Extract the numeric ID from the URL: /anime/{slug}-{id}
                extra = mapOf("id" to link.substringAfterLast("-"))
            )
        }
    } ?: emptyList()

    /**
     * Load episodes from the anime detail page.
     * Anime page: GET /anime/{slug}-{id}
     * The page is server-rendered HTML and contains an episode list.
     *
     * Expected HTML structure:
     *   <div class="episode-list"> or similar container
     *   Each episode: <a href="/watch/{slug}-{id}?ep={n}"> or <a href="/anime/{slug}-{id}?ep={n}">
     *   Contains episode number and title
     */
    override suspend fun loadEpisodes(animeLink: String, extra: Map<String, String>?): List<Episode> = tryWithSuspend {
        val url = animeLink.let {
            // If it's just an ID, construct the full URL
            if (it.startsWith("/") || it.startsWith("http")) it
            else {
                // If extra has the anime slug, use it; otherwise try to search
                val slug = extra?.get("slug") ?: return@tryWithSuspend emptyList()
                "/anime/$slug-$it"
            }
        }
        val fullUrl = if (url.startsWith("http")) url else "$hostUrl$url"
        val doc = client.get(fullUrl, mapOf("referer" to hostUrl)).document

        // Try common episode list selectors — will need adjustment based on actual page structure
        val episodeElements = doc.select("[data-episode], .episode, .ep-list a, [href*=\"ep=\"]")
            .ifEmpty { doc.select("a[href*=\"/watch/\"]") }
            .ifEmpty { doc.select("a[href*=\"episode\"]") }

        episodeElements.mapNotNull { el ->
            val epLink = el.attr("href").trim()
            val epNum = extractEpisodeNumber(el, epLink) ?: return@mapNotNull null
            val epTitle = el.ownText().ifEmpty {
                el.selectFirst(".title, .name, span")?.text() ?: "Episode $epNum"
            }
            val thumb = el.selectFirst("img")?.attr("src") ?: ""

            Episode(
                number = epNum.toString(),
                link = epLink,
                title = epTitle,
                thumbnail = FileUrl(thumb)
            )
        }.sortedBy { it.number.toIntOrNull() ?: 0 }
    } ?: emptyList()

    /**
     * Load video servers from the episode/watch page.
     * Watch page: GET /watch/{slug}-{id}?ep={n}
     * The page contains a video player with source URLs (likely HLS/m3u8).
     *
     * Video sources could be:
     * 1. Direct m3u8 URLs in <source> or data- attributes
     * 2. Embedded in a <script> tag with JSON config
     * 3. From a server selector (sub/dub)
     */
    override suspend fun loadVideoServers(episodeLink: String, extra: Any?): List<VideoServer> = tryWithSuspend {
        val url = if (episodeLink.startsWith("http")) episodeLink else "$hostUrl$episodeLink"
        val doc = client.get(url, mapOf("referer" to hostUrl)).document

        val servers = mutableListOf<VideoServer>()

        // 1. Check for direct video sources
        doc.select("video source, source[src]").forEach { source ->
            val src = source.attr("src")
            val type = source.attr("type")
            val quality = source.attr("data-res, data-quality, label")
                .ifEmpty { source.attr("title") }
                .ifEmpty { "Auto" }

            if (src.isNotBlank() && (src.contains(".m3u8") || src.contains(".mp4"))) {
                servers.add(
                    VideoServer(
                        name = "AniDb $quality",
                        embedUrl = FileUrl(src, mapOf("referer" to hostUrl)),
                        extraData = mapOf(
                            "url" to src,
                            "quality" to quality,
                            "referer" to hostUrl
                        )
                    )
                )
            }
        }

        // 2. Check for data- attributes with source URLs
        doc.select("[data-src], [data-url], [data-video]").forEach { el ->
            val src = el.attr("data-src").ifEmpty { el.attr("data-url").ifEmpty { el.attr("data-video") } }
            if (src.isNotBlank() && src.contains(".m3u8")) {
                servers.add(
                    VideoServer(
                        name = "AniDb HD",
                        embedUrl = FileUrl(src, mapOf("referer" to hostUrl)),
                        extraData = mapOf("url" to src, "quality" to "HD", "referer" to hostUrl)
                    )
                )
            }
        }

        // 3. Check for Alpine.js data or script configs
        doc.select("script:not([src])").forEach { script ->
            val content = script.html()
            if (content.contains(".m3u8") || content.contains("video_src") || content.contains("player")) {
                val m3u8Match = Regex("""https?://[^\"'\s]+\.m3u8[^\"'\s]*""").find(content)
                if (m3u8Match != null) {
                    servers.add(
                        VideoServer(
                            name = "AniDb",
                            embedUrl = FileUrl(m3u8Match.value, mapOf("referer" to hostUrl)),
                            extraData = mapOf("url" to m3u8Match.value, "quality" to "Auto", "referer" to hostUrl)
                        )
                    )
                }
            }
        }

        // 4. If no servers found, return the watch page URL as an embed
        //    (some video hosts provide the URL in JavaScript after page load)
        if (servers.isEmpty()) {
            servers.add(
                VideoServer(
                    name = "AniDb",
                    embedUrl = FileUrl(url),
                    extraData = mapOf("url" to url, "quality" to "Embed", "referer" to hostUrl)
                )
            )
        }

        servers.distinctBy { it.name }
    } ?: emptyList()

    override suspend fun getVideoExtractor(server: VideoServer): VideoExtractor =
        AniDbExtractor(server)

    class AniDbExtractor(override val server: VideoServer) : VideoExtractor() {
        @Suppress("UNCHECKED_CAST")
        override suspend fun extract(): VideoContainer {
            val data = (server.extraData as? Map<String, Any>) ?: return VideoContainer(emptyList())
            val url = data["url"] as? String ?: server.embedUrl.url ?: return VideoContainer(emptyList())
            val quality = (data["quality"] as? String)?.substringBefore("p")?.toIntOrNull() ?: 0
            val referer = data["referer"] as? String ?: ""

            val videoType = when {
                url.contains(".m3u8") -> VideoType.M3U8
                url.contains(".mp4") -> VideoType.MP4
                else -> VideoType.M3U8
            }

            return VideoContainer(
                videos = listOf(
                    Video(
                        quality = quality,
                        type = videoType,
                        link = FileUrl(url, mapOf("referer" to referer))
                    )
                ),
                subtitles = emptyList()
            )
        }
    }

    companion object {
        private val EPISODE_NUM_REGEX = Regex("""(?:ep[-=](\d+)|(?:/|-)ep[-.]?(\d+)|(?:episode[-_ ](\d+)))""", RegexOption.IGNORE_CASE)
        private val EPISODE_TEXT_REGEX = Regex("""(?:^|\s+)(\d+)\s*$""")
    }

    /**
     * Extract episode number from element text or link URL.
     */
    private fun extractEpisodeNumber(el: Element, link: String): Int? {
        // From link URL
        val urlMatch = EPISODE_NUM_REGEX.find(link)
        if (urlMatch != null) {
            return (urlMatch.groupValues.drop(1).firstOrNull { it.isNotEmpty() })?.toIntOrNull()
        }

        // From element attributes
        val epAttr = el.attr("data-episode").ifEmpty { el.attr("data-number") }
        if (epAttr.isNotBlank()) return epAttr.toIntOrNull()

        // From element text content
        val text = el.text().trim()
        val textMatch = EPISODE_TEXT_REGEX.find(text)
        if (textMatch != null) {
            return textMatch.groupValues[1].toIntOrNull()
        }

        return null
    }
}
