package com.shilapi.xcertplay.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29])
class UpdateCatalogTest {
    private val releaseJson = """
        [
          {
            "tag_name": "v0.2.17",
            "draft": true,
            "prerelease": true,
            "html_url": "https://github.com/Qwy20040320/carpaly/releases/tag/v0.2.17",
            "body": "preview notes",
            "assets": [
              {"name": "CarPaly-XingyueL.apk", "browser_download_url": "https://github.com/Qwy20040320/carpaly/releases/download/v0.2.17/CarPaly-XingyueL.apk", "size": 23000000, "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
            ]
          },
          {
            "tag_name": "v0.2.16",
            "draft": false,
            "prerelease": true,
            "html_url": "https://github.com/Qwy20040320/carpaly/releases/tag/v0.2.16",
            "body": "v0.2.16 preview notes",
            "assets": [
              {"name": "CarPaly-XingyueL.apk", "browser_download_url": "https://github.com/Qwy20040320/carpaly/releases/download/v0.2.16/CarPaly-XingyueL.apk", "size": 22388239, "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
            ]
          }
        ]
    """.trimIndent()

    @Test
    fun skipsDraftsAndReturnsTheFirstPublishedCarPalyReleaseWithMetadata() {
        val release = UpdateCatalog.parse(releaseJson)
        assertEquals("v0.2.16", release?.tagName)
        assertEquals("CarPaly-XingyueL.apk", release?.apkName)
        assertEquals(
            "https://github.com/Qwy20040320/carpaly/releases/download/v0.2.16/CarPaly-XingyueL.apk",
            release?.apkUrl,
        )
        assertEquals("https://github.com/Qwy20040320/carpaly/releases/tag/v0.2.16", release?.releasePageUrl)
        assertEquals("v0.2.16 preview notes", release?.releaseNotes)
        assertEquals(22_388_239L, release?.sizeBytes)
        assertEquals(true, release?.isPrerelease)
        assertEquals("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", release?.sha256)
    }

    @Test
    fun ignoresOtherRepositoriesAndNonCanonicalApkNames() {
        val json = """
            [{"tag_name":"v0.2.14","draft":false,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v0.2.14","assets":[
              {"name":"DiPlay.apk","browser_download_url":"https://github.com/shihabal3amri/DiPlay/releases/download/v0.2.14/DiPlay.apk","size":10,"digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
            ]}]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun requiresTheGitHubProvidedSha256Digest() {
        val json = """
            [{"tag_name":"v0.2.14","draft":false,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v0.2.14","assets":[
              {"name":"CarPaly-XingyueL.apk","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v0.2.14/CarPaly-XingyueL.apk","size":200,"digest":""}
            ]}]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun requiresANonZeroAssetSizeForTheReleasePrompt() {
        val json = """
            [{"tag_name":"v0.2.14","draft":false,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v0.2.14","assets":[
              {"name":"CarPaly-XingyueL.apk","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v0.2.14/CarPaly-XingyueL.apk","size":0,"digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
            ]}]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun rejectsNonGithubDownloadUrls() {
        val json = """
            [{"tag_name":"v0.2.16","draft":false,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v0.2.16","assets":[
              {"name":"CarPaly-XingyueL.apk","browser_download_url":"https://example.com/CarPaly-XingyueL.apk","size":200,"digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
            ]}]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun rejectsReleasePagesOutsideTheCanonicalRepository() {
        val json = """
            [{"tag_name":"v0.2.16","draft":false,"html_url":"https://github.com/other/project/releases/tag/v0.2.16","assets":[
              {"name":"CarPaly-XingyueL.apk","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v0.2.16/CarPaly-XingyueL.apk","size":100,"digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
            ]}]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun doesNotFallBackToAnOlderReleaseWhenNewestPublishedReleaseIsIncomplete() {
        val json = """
            [
              {"tag_name":"v0.2.17","draft":false,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v0.2.17","assets":[]},
              {"tag_name":"v0.2.16","draft":false,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v0.2.16","assets":[
                {"name":"CarPaly-XingyueL.apk","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v0.2.16/CarPaly-XingyueL.apk","size":100,"digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
              ]}
            ]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun returnsNullForAnEmptyReleaseList() {
        assertNull(UpdateCatalog.parse("[]"))
    }

    @Test
    fun releaseApiTargetsOnlyTheCarPalyRepository() {
        assertEquals(
            "https://api.github.com/repos/Qwy20040320/carpaly/releases?per_page=10",
            UpdateClient.RELEASES_URL,
        )
    }
}
