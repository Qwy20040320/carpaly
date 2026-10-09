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
            "assets": [
              {"name": "CarPaly-XingyueL.apk", "browser_download_url": "https://github.com/Qwy20040320/carpaly/releases/download/v0.2.17/CarPaly-XingyueL.apk", "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
            ]
          },
          {
            "tag_name": "v0.2.16",
            "draft": false,
            "prerelease": true,
            "assets": [
              {"name": "CarPaly-XingyueL.apk", "browser_download_url": "https://github.com/Qwy20040320/carpaly/releases/download/v0.2.16/CarPaly-XingyueL.apk", "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
            ]
          }
        ]
    """.trimIndent()

    @Test
    fun skipsDraftsAndReturnsTheFirstPublishedCarPalyRelease() {
        val release = UpdateCatalog.parse(releaseJson)
        assertEquals("v0.2.16", release?.tagName)
        assertEquals("CarPaly-XingyueL.apk", release?.apkName)
        assertEquals(
            "https://github.com/Qwy20040320/carpaly/releases/download/v0.2.16/CarPaly-XingyueL.apk",
            release?.apkUrl,
        )
        assertEquals("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", release?.sha256)
    }

    @Test
    fun ignoresOtherRepositoriesAndNonCanonicalApkNames() {
        val json = """
            [
              {"tag_name": "v0.2.14", "draft": false, "assets": [
                {"name": "DiPlay.apk", "browser_download_url": "https://github.com/shihabal3amri/DiPlay/releases/download/v0.2.14/DiPlay.apk", "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
              ]}
            ]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun requiresTheGitHubProvidedSha256Digest() {
        val json = """
            [
              {"tag_name": "v0.2.14", "draft": false, "assets": [
                {"name": "CarPaly-XingyueL.apk", "browser_download_url": "https://github.com/Qwy20040320/carpaly/releases/download/v0.2.14/CarPaly-XingyueL.apk"}
              ]}
            ]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun rejectsNonGithubDownloadUrls() {
        val json = """
            [{"tag_name":"v0.2.16","draft":false,"assets":[
              {"name":"CarPaly-XingyueL.apk","browser_download_url":"https://example.com/CarPaly-XingyueL.apk","digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
            ]}]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun doesNotFallBackToAnOlderReleaseWhenNewestPublishedReleaseIsIncomplete() {
        val json = """
            [
              {"tag_name":"v0.2.17","draft":false,"assets":[]},
              {"tag_name":"v0.2.16","draft":false,"assets":[
                {"name":"CarPaly-XingyueL.apk","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v0.2.16/CarPaly-XingyueL.apk","digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
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
