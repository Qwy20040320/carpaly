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
            "tag_name": "v1.1.6",
            "draft": true,
            "prerelease": true,
            "html_url": "https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.6",
            "body": "draft notes",
            "assets": [
              {"name": "CarPaly-XingyueL1.1.6.apk", "browser_download_url": "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.6/CarPaly-XingyueL1.1.6.apk", "size": 23000000, "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
              {"name": "CarPaly-XingyueL1.1.6.apk.sha256", "browser_download_url": "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.6/CarPaly-XingyueL1.1.6.apk.sha256", "size": 92}
            ]
          },
          {
            "tag_name": "v1.1.5",
            "draft": false,
            "prerelease": true,
            "html_url": "https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.5",
            "body": "preview notes",
            "assets": [
              {"name": "CarPaly-XingyueL1.1.5.apk", "browser_download_url": "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.5/CarPaly-XingyueL1.1.5.apk", "size": 23000000, "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
              {"name": "CarPaly-XingyueL1.1.5.apk.sha256", "browser_download_url": "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.5/CarPaly-XingyueL1.1.5.apk.sha256", "size": 92}
            ]
          },
          {
            "tag_name": "v1.1.4",
            "draft": false,
            "prerelease": false,
            "html_url": "https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.4",
            "body": "stable notes",
            "assets": [
              {"name": "CarPaly-XingyueL1.1.4.apk", "browser_download_url": "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.4/CarPaly-XingyueL1.1.4.apk", "size": 22388239, "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
              {"name": "CarPaly-XingyueL1.1.4.apk.sha256", "browser_download_url": "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.4/CarPaly-XingyueL1.1.4.apk.sha256", "size": 92}
            ]
          }
        ]
    """.trimIndent()

    @Test
    fun previewChannelSkipsDraftsAndReturnsTheNewestVersionedCarPalyApk() {
        val release = UpdateCatalog.parse(releaseJson)
        assertEquals("v1.1.5", release?.tagName)
        assertEquals("1.1.5", release?.versionName)
        assertEquals("CarPaly-XingyueL1.1.5.apk", release?.apkName)
        assertEquals(
            "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.5/CarPaly-XingyueL1.1.5.apk",
            release?.apkUrl,
        )
        assertEquals(
            "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.5/CarPaly-XingyueL1.1.5.apk.sha256",
            release?.checksumUrl,
        )
        assertEquals(92L, release?.checksumSizeBytes)
        assertEquals("https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.5", release?.releasePageUrl)
        assertEquals("preview notes", release?.releaseNotes)
        assertEquals(23_000_000L, release?.sizeBytes)
        assertEquals(true, release?.isPrerelease)
        assertEquals("a".repeat(64), release?.sha256)
    }

    @Test
    fun stableChannelIgnoresPreviewsAndReturnsTheNewestStableRelease() {
        val release = UpdateCatalog.parse(releaseJson, UpdateChannel.STABLE)
        assertEquals("v1.1.4", release?.tagName)
        assertEquals("1.1.4", release?.versionName)
        assertEquals(false, release?.isPrerelease)
    }

    @Test
    fun versionNameDrivesTheExpectedApkName() {
        assertEquals("CarPaly-XingyueL1.1.10.apk", UpdateCatalog.apkName("1.1.10"))
    }

    @Test
    fun choosesTheNumericallyNewestReleaseInsteadOfRelyingOnApiOrder() {
        val json = """
            [
              {"tag_name":"v1.1.9","draft":false,"prerelease":true,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.9","assets":[
                {"name":"CarPaly-XingyueL1.1.9.apk","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v1.1.9/CarPaly-XingyueL1.1.9.apk","size":100,"digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
                {"name":"CarPaly-XingyueL1.1.9.apk.sha256","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v1.1.9/CarPaly-XingyueL1.1.9.apk.sha256","size":92}
              ]},
              {"tag_name":"v1.1.10","draft":false,"prerelease":true,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.10","assets":[
                {"name":"CarPaly-XingyueL1.1.10.apk","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v1.1.10/CarPaly-XingyueL1.1.10.apk","size":100,"digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
                {"name":"CarPaly-XingyueL1.1.10.apk.sha256","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v1.1.10/CarPaly-XingyueL1.1.10.apk.sha256","size":93}
              ]}
            ]
        """.trimIndent()

        assertEquals("v1.1.10", UpdateCatalog.parse(json)?.tagName)
    }

    @Test
    fun skipsAnIncompleteNewerReleaseAndUsesAnOlderValidRelease() {
        val json = """
            [
              {"tag_name":"v1.1.6","draft":false,"prerelease":true,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.6","assets":[]},
              {"tag_name":"v1.1.5","draft":false,"prerelease":true,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.5","assets":[
                {"name":"CarPaly-XingyueL1.1.5.apk","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v1.1.5/CarPaly-XingyueL1.1.5.apk","size":100,"digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
                {"name":"CarPaly-XingyueL1.1.5.apk.sha256","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v1.1.5/CarPaly-XingyueL1.1.5.apk.sha256","size":92}
              ]}
            ]
        """.trimIndent()
        assertEquals("v1.1.5", UpdateCatalog.parse(json)?.tagName)
    }

    @Test
    fun ignoresLegacyUnversionedAssetsInsteadOfTreatingHistoryAsNewVersionedReleases() {
        val json = """
            [{"tag_name":"v0.2.16","draft":false,"prerelease":true,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v0.2.16","assets":[
              {"name":"CarPaly-XingyueL.apk","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v0.2.16/CarPaly-XingyueL.apk","size":22388239,"digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
            ]}]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun skipsVersionedReleasesFromBeforeTheAuthenticatedDistributionBoundary() {
        val json = """
            [{"tag_name":"v1.1.3","draft":false,"prerelease":false,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.3","assets":[
              {"name":"CarPaly-XingyueL1.1.3.apk","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v1.1.3/CarPaly-XingyueL1.1.3.apk","size":200,"digest":"sha256:${"0".repeat(64)}"}
            ]}]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun ignoresOtherRepositoriesAndNonCanonicalApkNames() {
        val json = """
            [{"tag_name":"v1.1.4","draft":false,"prerelease":true,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.4","assets":[
              {"name":"DiPlay.apk","browser_download_url":"https://github.com/shihabal3amri/DiPlay/releases/download/v1.1.4/DiPlay.apk","size":10,"digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
            ]}]
        """.trimIndent()
        assertNull(UpdateCatalog.parse(json))
    }

    @Test
    fun requiresTheGitHubProvidedSha256DigestAndNonZeroSize() {
        val noDigest = """
            [{"tag_name":"v1.1.4","draft":false,"prerelease":true,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.4","assets":[
              {"name":"CarPaly-XingyueL1.1.4.apk","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v1.1.4/CarPaly-XingyueL1.1.4.apk","size":200,"digest":""},
              {"name":"CarPaly-XingyueL1.1.4.apk.sha256","browser_download_url":"https://github.com/Qwy20040320/carpaly/releases/download/v1.1.4/CarPaly-XingyueL1.1.4.apk.sha256","size":92}
            ]}]
        """.trimIndent()
        val noSize = noDigest.replace("\"size\":200", "\"size\":0")
            .replace("\"digest\":\"\"", "\"digest\":\"sha256:${"0".repeat(64)}\"")
        assertNull(UpdateCatalog.parse(noDigest))
        assertNull(UpdateCatalog.parse(noSize))
    }

    @Test
    fun skipsApksLargerThanTheSupportedDownloadLimit() {
        val oversizedSize = UpdateApkDownloader.MAX_APK_BYTES + 1
        val oversizedJson = Regex("(\"size\"\\s*:\\s*)23000000")
            .replace(releaseJson) { match -> "${match.groupValues[1]}$oversizedSize" }
        assertEquals(2, Regex("\"size\"\\s*:\\s*$oversizedSize").findAll(oversizedJson).count())
        assertEquals("v1.1.4", UpdateCatalog.parse(oversizedJson)?.tagName)
    }

    @Test
    fun rejectsNonCanonicalReleaseAndDownloadUrls() {
        val badPage = releaseJson.replace(
            "https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.5",
            "https://github.com/other/project/releases/tag/v1.1.5",
        )
        val badAsset = releaseJson.replace(
            "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.5/CarPaly-XingyueL1.1.5.apk",
            "https://example.com/CarPaly-XingyueL1.1.5.apk",
        )
        assertEquals("v1.1.4", UpdateCatalog.parse(badPage)?.tagName)
        assertEquals("v1.1.4", UpdateCatalog.parse(badAsset)?.tagName)
    }

    @Test
    fun rejectsReleaseTagsThatDoNotMatchTheIndependentVersionFormat() {
        val json = """
            [{"tag_name":"release-1.1.4","draft":false,"prerelease":true,"html_url":"https://github.com/Qwy20040320/carpaly/releases/tag/release-1.1.4","assets":[]}]
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
            "https://api.github.com/repos/Qwy20040320/carpaly/releases?per_page=30",
            UpdateClient.RELEASES_URL,
        )
    }
}
