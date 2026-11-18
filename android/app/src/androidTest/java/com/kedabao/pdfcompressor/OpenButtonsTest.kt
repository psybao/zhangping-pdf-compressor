package com.kedabao.pdfcompressor
import android.app.Activity
import android.app.Instrumentation
import android.content.Intent
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.lifecycle.ViewModelProvider
import androidx.core.content.FileProvider
import org.junit.Test
import org.junit.Assert.*
import org.junit.runner.RunWith
import java.io.File
import java.util.concurrent.atomic.AtomicReference
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performClick
import org.junit.Rule
@RunWith(AndroidJUnit4::class)
class OpenButtonsTest {
    @get:Rule val compose=createEmptyComposeRule()
    @Test fun sourceAndResultStaySeparate() {
        val inst=InstrumentationRegistry.getInstrumentation();val ctx=inst.targetContext
        val source=File(ctx.filesDir,"results/routing_source.pdf");source.parentFile!!.mkdirs()
        inst.context.assets.open("text.pdf").use{input->source.outputStream().use{input.copyTo(it)}}
        val sourceUri=FileProvider.getUriForFile(ctx,"${ctx.packageName}.files",source)
        val launched=AtomicReference<Intent?>()
        val monitor=object:Instrumentation.ActivityMonitor(){
            override fun onStartActivity(intent:Intent):Instrumentation.ActivityResult? {
                if(intent.action==Intent.ACTION_CHOOSER){launched.set(intent.getParcelableExtra(Intent.EXTRA_INTENT));return Instrumentation.ActivityResult(Activity.RESULT_CANCELED,null)}
                return null
            }
        }
        fun click(text:String) {
            compose.waitForIdle()
            compose.onNodeWithText(text,useUnmergedTree=true).performScrollTo().performClick()
            compose.waitForIdle()
        }
        lateinit var model:PdfModel
        fun awaitReady(){val until=System.currentTimeMillis()+60000;while(true){var busy=true;inst.runOnMainSync{busy=model.busy};if(!busy)return;assertTrue(System.currentTimeMillis()<until);Thread.sleep(100)}}
        inst.addMonitor(monitor)
        try { ActivityScenario.launch(MainActivity::class.java).use{scenario->
            scenario.onActivity{a->model=ViewModelProvider(a)[PdfModel::class.java];model.closeGuide();model.clear();model.add(listOf(sourceUri))}
            awaitReady();click("打开");assertEquals(sourceUri,launched.get()?.data)
            scenario.onActivity{model.targetMode=false;model.estimateAll()};awaitReady();scenario.onActivity{model.start()};awaitReady()
            var output:String?=null;scenario.onActivity{assertTrue(model.entries.single().success);output=model.entries.single().output}
            launched.set(null);click("打开");assertEquals(sourceUri,launched.get()?.data)
            launched.set(null);click("压缩后文件");assertEquals(output,launched.get()?.data.toString());assertNotEquals(sourceUri.toString(),output)
            File(ctx.filesDir,"test_results").mkdirs();File(ctx.filesDir,"test_results/open_buttons.txt").writeText("PASS: actual button clicks captured ACTION_VIEW intents; Open targets original URI both before/after compression; Compressed File targets output URI only.")
            scenario.onActivity{model.clear()}
        }} finally {inst.removeMonitor(monitor)}
    }
}
