package com.kedabao.pdfcompressor

import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.runBlocking
import org.junit.Test
import org.junit.Assert.*
import org.junit.runner.RunWith
import java.io.File
import org.json.JSONArray
import org.json.JSONObject

@RunWith(AndroidJUnit4::class)
class EngineTest {
    @Test fun realCompressionMatrix() = runBlocking {
        val inst=InstrumentationRegistry.getInstrumentation()
        val context=inst.targetContext
        val engine=PdfEngine(context)
        val rows=JSONArray()
        val folder=File(context.filesDir,"test_results").apply{mkdirs()}
        for(name in listOf("text","scan","mixed","large","multipage","transparency","compressed")) {
            val source=File(folder,"$name.pdf")
            inst.context.assets.open("$name.pdf").use{src->source.outputStream().use{src.copyTo(it)}}
            val boxes=engine.verify(source);val text=engine.text(source)
            for(mode in listOf("HIGH","MEDIUM","LOW","500KB","1MB")) {
                val target=when(mode){"500KB"->512000L;"1MB"->1048576L;else->null}
                val r=engine.compress(source,if(target==null)mode else "MEDIUM",target)
                assertTrue(r.after<=r.before);assertEquals(boxes,engine.verify(r.file));assertEquals(text,engine.text(r.file));assertEquals(target==null || r.after<=target,r.met)
                assertTrue(r.attempts<=12)
                ParcelFileDescriptor.open(r.file,ParcelFileDescriptor.MODE_READ_ONLY).use{fd->PdfRenderer(fd).use{renderer->assertEquals(boxes.size,renderer.pageCount);renderer.openPage(0).use{page->val bitmap=android.graphics.Bitmap.createBitmap(306,396,android.graphics.Bitmap.Config.ARGB_8888);page.render(bitmap,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);bitmap.recycle()}}}
                rows.put(JSONObject().put("file",name).put("mode",mode).put("before",r.before).put("after",r.after).put("met",r.met).put("attempts",r.attempts))
                File(folder,"results.json").writeText(JSONObject().put("passed",false).put("rows",rows).toString(2))
            }
        }
        for(name in listOf("encrypted","empty","broken","signed")) {
            val source=File(folder,"$name.pdf");inst.context.assets.open("$name.pdf").use{src->source.outputStream().use{src.copyTo(it)}}
            var rejected=false;try{engine.compress(source)}catch(e:Exception){rejected=true};assertTrue("$name must be rejected",rejected)
        }
        assertEquals(512000,engine.spec.getJSONObject("units").getInt("KB")*500)
        assertEquals(1048576,engine.spec.getJSONObject("units").getInt("MB"))
        val tiny=engine.compress(File(folder,"text.pdf"),target=1);assertFalse(tiny.met)
        File(folder,"results.json").writeText(JSONObject().put("passed",true).put("rows",rows).put("checks","35 actual compressions, page boxes, text extraction equality, Android PdfRenderer open/render, encrypted/empty/broken/signed rejection, target too small, units").toString(2))
    }
}
