package com.kedabao.pdfcompressor
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.runBlocking
import org.junit.Test
import org.junit.Assert.*
import org.junit.runner.RunWith
import java.io.File
@RunWith(AndroidJUnit4::class)
class QuickEstimateTest {
    @Test fun metadataOnlyPreview()=runBlocking {
        val inst=InstrumentationRegistry.getInstrumentation();val ctx=inst.targetContext;val engine=PdfEngine(ctx)
        val cache=File(ctx.cacheDir,"pdf_candidates");val before=cache.list()?.toSet()?:emptySet<String>()
        val start=System.nanoTime()
        for(name in listOf("text","scan","mixed","large","multipage","transparency","compressed")) {
            val src=File(ctx.cacheDir,"preview_$name.pdf");inst.context.assets.open("$name.pdf").use{input->src.outputStream().use{input.copyTo(it)}}
            for(mode in listOf("HIGH","MEDIUM","LOW","500KB","1MB","2MB","1BYTE")) {
                val target=when(mode){"500KB"->512000L;"1MB"->1048576L;"2MB"->2097152L;"1BYTE"->1L;else->null}
                val r=engine.quickEstimate(src,if(target==null)mode else "MEDIUM",target)
                assertTrue(r.lower>0 && r.lower<=r.after && r.after<=r.upper && r.upper<=minOf(src.length(),target?:Long.MAX_VALUE))
            }
            src.delete()
        }
        assertEquals(before,cache.list()?.toSet()?:emptySet<String>())
        File(ctx.filesDir,"test_results").mkdirs()
        File(ctx.filesDir,"test_results/quick_estimate.txt").writeText("PASS: 49 metadata-only preview cases; 2MB/1MB/500KB/1byte preview and range caps; no candidate PDF generated; elapsed including copying fixtures: ${(System.nanoTime()-start)/1e9}s")
    }
}
