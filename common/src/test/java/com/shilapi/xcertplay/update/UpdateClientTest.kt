package com.shilapi.xcertplay.update

import com.sun.net.httpserver.HttpServer
import java.net.InetAddress
import java.net.InetSocketAddress
import java.util.concurrent.Executors
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class UpdateClientTest {
    private lateinit var server: HttpServer
    private lateinit var root: String

    @Before
    fun startServer() {
        server = HttpServer.create(InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0)
        root = "http://${server.address.hostString}:${server.address.port}"
        server.executor = Executors.newSingleThreadExecutor()
        server.start()
    }

    @After
    fun stopServer() {
        server.stop(0)
    }

    @Test
    fun fetchTextReturnsTheBody() {
        val body = "[{\"tag_name\": \"v0.2.14\"}]"
        server.createContext("/releases") { exchange ->
            val bytes = body.toByteArray()
            exchange.responseHeaders.add("Content-Type", "application/json")
            exchange.sendResponseHeaders(200, bytes.size.toLong())
            exchange.responseBody.use { it.write(bytes) }
        }
        assertEquals(body, UpdateClient.fetchText("$root/releases", "application/vnd.github+json", "DiPlay/test"))
    }

    @Test
    fun fetchTextFailsOnHttpErrors() {
        server.createContext("/releases") { exchange ->
            exchange.sendResponseHeaders(403, -1)
            exchange.close()
        }
        try {
            UpdateClient.fetchText("$root/releases", null, "DiPlay/test")
            throw AssertionError("expected an IOException")
        } catch (expected: java.io.IOException) {
            assertTrue(expected.message!!.contains("403"))
        }
    }

}
