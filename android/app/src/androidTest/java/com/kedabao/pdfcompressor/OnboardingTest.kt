package com.kedabao.pdfcompressor
import android.view.accessibility.AccessibilityNodeInfo
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.Assert.*
import org.junit.runner.RunWith
import java.io.File
@RunWith(AndroidJUnit4::class)
class OnboardingTest {
    @Test fun firstLaunchAndHelpButton() {
        val inst=InstrumentationRegistry.getInstrumentation();val ctx=inst.targetContext
        ctx.getSharedPreferences("usage",0).edit().clear().commit()
        fun find(node:AccessibilityNodeInfo?,text:String):AccessibilityNodeInfo? {
            if(node==null)return null
            if(node.text?.toString()?.contains(text)==true)return node
            for(i in 0 until node.childCount){val found=find(node.getChild(i),text);if(found!=null)return found}
            return null
        }
        fun waitFor(text:String):AccessibilityNodeInfo {
            val until=System.currentTimeMillis()+10000
            while(System.currentTimeMillis()<until){find(inst.uiAutomation.rootInActiveWindow,text)?.let{return it};Thread.sleep(100)}
            error("Missing UI text: $text")
        }
        fun click(text:String){var n=waitFor(text);while(!n.isClickable && n.parent!=null)n=n.parent;assertTrue(n.performAction(AccessibilityNodeInfo.ACTION_CLICK));inst.waitForIdleSync()}
        ActivityScenario.launch(MainActivity::class.java).use {
            waitFor("1 / 4")
            File(ctx.filesDir,"test_results").mkdirs()
            inst.uiAutomation.takeScreenshot().let{bitmap->File(ctx.filesDir,"test_results/ui_guide.png").outputStream().use{out->bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG,100,out)};bitmap.recycle()}
            click("下一步");waitFor("2 / 4");click("下一步");waitFor("3 / 4");click("下一步");waitFor("4 / 4");click("完成，开始使用")
            assertTrue(ctx.getSharedPreferences("usage",0).getBoolean("guide_seen",false))
            click("?");waitFor("1 / 4");click("关闭")
        }
        ActivityScenario.launch(MainActivity::class.java).use {inst.waitForIdleSync();assertNull(find(inst.uiAutomation.rootInActiveWindow,"四步完成 PDF 压缩"))}
        File(ctx.filesDir,"test_results/onboarding.txt").writeText("PASS: actual accessibility clicks through four guide steps, finish persists state, top-right help reopens guide, subsequent Activity launch does not show guide.")
    }
}
