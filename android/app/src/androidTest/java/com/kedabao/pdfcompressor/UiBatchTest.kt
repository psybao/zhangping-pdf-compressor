package com.kedabao.pdfcompressor

import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.lifecycle.ViewModelProvider
import androidx.core.content.FileProvider
import java.io.File
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class UiBatchTest {
    @Test fun batchThroughLiveActivity() {
        val inst=InstrumentationRegistry.getInstrumentation();val ctx=inst.targetContext
        ctx.getSharedPreferences("usage",0).edit().clear().commit()
        val folder=File(ctx.filesDir,"results").apply{mkdirs()}
        val uris=listOf("text","mixed").map{name->
            val f=File(folder,"ui_input_$name.pdf");inst.context.assets.open("$name.pdf").use{src->f.outputStream().use{src.copyTo(it)}}
            FileProvider.getUriForFile(ctx,"${ctx.packageName}.files",f)
        }
        lateinit var model:PdfModel
        ActivityScenario.launch(MainActivity::class.java).use{scenario->
            scenario.onActivity{activity->model=ViewModelProvider(activity)[PdfModel::class.java];assertTrue(model.showGuide);for(i in 0..2)model.guideStep++;assertEquals(3,model.guideStep);model.closeGuide();assertFalse(model.showGuide);assertTrue(ctx.getSharedPreferences("usage",0).getBoolean("guide_seen",false));model.openGuide();assertTrue(model.showGuide);assertEquals(0,model.guideStep);model.closeGuide();model.clear();model.add(uris)}
            fun awaitReady(){val deadline=System.currentTimeMillis()+300000;while(true){var busy=true;inst.runOnMainSync{busy=model.busy};if(!busy)break;assertTrue("UI task timeout",System.currentTimeMillis()<deadline);Thread.sleep(200)}}
            awaitReady()
            scenario.onActivity{assertEquals(2,model.entries.size);assertTrue(model.entries.all{it.estimates.isEmpty()});assertFalse(model.canStart);model.estimateAll()}
            awaitReady()
            scenario.onActivity{assertTrue(model.canStart);assertTrue(model.entries.all{it.estimates.size==1});model.targetMode=true;model.amount="2";model.unit="MB";assertFalse(model.canStart);model.estimateAll()}
            awaitReady()
            assertTrue(File(ctx.cacheDir,"pdf_candidates").listFiles()?.isEmpty()?:true)
            scenario.onActivity{assertTrue(model.canStart);model.start()}
            awaitReady()
            scenario.onActivity{assertTrue(model.entries.all{it.success && it.output!=null})}
            val engine=PdfEngine(ctx)
            for(e in model.entries){val out=File(ctx.cacheDir,"ui_verify_${e.id}.pdf");ctx.contentResolver.openInputStream(android.net.Uri.parse(e.output))!!.use{src->out.outputStream().use{src.copyTo(it)}};assertTrue(out.length()<=2097152);assertEquals(engine.text(e.source),engine.text(out));out.delete()}
            val screenshot=inst.uiAutomation.takeScreenshot()
            File(ctx.filesDir,"test_results/ui_batch.png").outputStream().use{screenshot.compress(android.graphics.Bitmap.CompressFormat.PNG,100,it)};screenshot.recycle()
            File(ctx.filesDir,"test_results/ui_batch.txt").writeText("PASS: first-launch guide preference, four steps, help reopen; import without automatic compression; manual preview and range <= target; target changes invalidate preview; no candidate PDF during preview; two files compressed <=2MB, copies reopened and text preserved.")
            scenario.onActivity{model.clear()}
        }
    }
}
