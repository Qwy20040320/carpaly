package com.shilapi.xcertplay.media

import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.fail
import org.junit.Test

class MediaCodecStartupTest {
    @Test fun configureFailureReleasesExactlyOnceAndNeverStarts() {
        val candidate = Any()
        val failure = IllegalArgumentException("configure rejected")
        var releases = 0
        try {
            MediaCodecStartup.create(
                create = { candidate },
                configure = { assertSame(candidate, it); throw failure },
                start = { fail("A rejected codec must not start") },
                release = { assertSame(candidate, it); releases++ },
            )
            fail("The original failure must propagate")
        } catch (actual: IllegalArgumentException) {
            assertSame(failure, actual)
        }
        assertEquals(1, releases)
    }

    @Test fun startFailureIsPreservedEvenIfReleaseAlsoFails() {
        val events = mutableListOf<String>()
        val failure = IllegalStateException("start rejected")
        try {
            MediaCodecStartup.create(
                create = { "codec" },
                configure = { events += "configure:$it" },
                start = { events += "start:$it"; throw failure },
                release = { events += "release:$it"; throw RuntimeException("release rejected") },
            )
            fail("The original failure must propagate")
        } catch (actual: IllegalStateException) {
            assertSame(failure, actual)
        }
        assertEquals(listOf("configure:codec", "start:codec", "release:codec"), events)
    }

    @Test fun linkageErrorsStillPropagateAfterReleasingTheCandidate() {
        val failure = NoSuchMethodError("platform API unavailable")
        var releases = 0
        try {
            MediaCodecStartup.create(
                create = { Any() }, configure = { throw failure },
                start = { fail("A rejected codec must not start") }, release = { releases++ },
            )
            fail("The platform error must propagate")
        } catch (actual: NoSuchMethodError) {
            assertSame(failure, actual)
        }
        assertEquals(1, releases)
    }

    @Test fun aWorkingCodecRemainsOwnedByTheRenderer() {
        val candidate = Any()
        assertSame(candidate, MediaCodecStartup.create(
            create = { candidate }, configure = {}, start = {},
            release = { fail("A started codec must remain alive") },
        ))
    }

    @Test fun creationFailureHasNoCandidateToRelease() {
        val failure = IllegalStateException("creation rejected")
        try {
            MediaCodecStartup.create<Any>(
                create = { throw failure }, configure = { fail("No candidate") },
                start = { fail("No candidate") }, release = { fail("No candidate") },
            )
            fail("The original failure must propagate")
        } catch (actual: IllegalStateException) {
            assertSame(failure, actual)
        }
    }

    @Test fun createFailureFallsBackToAnExplicitDecoderCandidate() {
        val events = mutableListOf<String>()
        val started = MediaCodecStartup.createWithFallback(
            candidates = listOf(
                MediaCodecStartup.Candidate("default") {
                    events += "create:default"
                    throw IllegalArgumentException("default decoder unavailable")
                },
                MediaCodecStartup.Candidate("software") {
                    events += "create:software"
                    "software-codec"
                },
            ),
            configure = { events += "configure:$it" },
            start = { events += "start:$it" },
            release = { events += "release:$it" },
            onFailure = { candidate, failure -> events += "failed:$candidate:${failure.javaClass.simpleName}" },
        )

        assertEquals("software", started.candidateName)
        assertEquals("software-codec", started.value)
        assertEquals(
            listOf("create:default", "failed:default:IllegalArgumentException", "create:software",
                "configure:software-codec", "start:software-codec"),
            events,
        )
    }

    @Test fun configureFailureReleasesCandidateThenTriesFallback() {
        val events = mutableListOf<String>()
        val started = MediaCodecStartup.createWithFallback(
            candidates = listOf(
                MediaCodecStartup.Candidate("default") { "default-codec" },
                MediaCodecStartup.Candidate("software") { "software-codec" },
            ),
            configure = {
                events += "configure:$it"
                if (it == "default-codec") throw IllegalArgumentException("configure rejected")
            },
            start = { events += "start:$it" },
            release = { events += "release:$it" },
        )

        assertEquals("software", started.candidateName)
        assertEquals("software-codec", started.value)
        assertEquals(
            listOf("configure:default-codec", "release:default-codec", "configure:software-codec",
                "start:software-codec"),
            events,
        )
    }

    @Test fun successfulFirstCandidateDoesNotTryFallback() {
        val started = MediaCodecStartup.createWithFallback(
            candidates = listOf(
                MediaCodecStartup.Candidate("default") { "default-codec" },
                MediaCodecStartup.Candidate("fallback") { fail("Fallback must not be created") },
            ),
            configure = {}, start = {}, release = { fail("Started codec remains owned") },
        )

        assertEquals("default", started.candidateName)
        assertEquals("default-codec", started.value)
    }

    @Test fun allCandidatesFailAndEarlierFailuresRemainSuppressed() {
        val first = IllegalArgumentException("default failed")
        val terminal = IllegalStateException("fallback failed")
        val releases = mutableListOf<String>()
        try {
            MediaCodecStartup.createWithFallback(
                candidates = listOf(
                    MediaCodecStartup.Candidate("default") { "default-codec" },
                    MediaCodecStartup.Candidate("fallback") { "fallback-codec" },
                ),
                configure = { if (it == "default-codec") throw first else throw terminal },
                start = { fail("A rejected codec must not start") },
                release = { releases += it },
            )
            fail("The final candidate failure must propagate")
        } catch (actual: IllegalStateException) {
            assertSame(terminal, actual)
            assertSame(first, actual.suppressed.single())
        }
        assertEquals(listOf("default-codec", "fallback-codec"), releases)
    }

    @Test fun errorIsReleasedAndRethrownWithoutTryingFallback() {
        val failure = NoSuchMethodError("codec API unavailable")
        var releases = 0
        var fallbackCreated = false
        try {
            MediaCodecStartup.createWithFallback(
                candidates = listOf(
                    MediaCodecStartup.Candidate("default") { "default-codec" },
                    MediaCodecStartup.Candidate("fallback") { fallbackCreated = true; "fallback-codec" },
                ),
                configure = { throw failure }, start = {}, release = { releases++ },
            )
            fail("Linkage errors must propagate")
        } catch (actual: NoSuchMethodError) {
            assertSame(failure, actual)
        }
        assertEquals(1, releases)
        assertEquals(false, fallbackCreated)
    }
}
