package com.kedabao.pdfcompressor

import android.content.Context
import android.graphics.Bitmap
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.contentstream.PDFStreamEngine
import com.tom_roush.pdfbox.contentstream.operator.Operator
import com.tom_roush.pdfbox.contentstream.operator.DrawObject
import com.tom_roush.pdfbox.contentstream.operator.state.*
import com.tom_roush.pdfbox.cos.*
import com.tom_roush.pdfbox.io.MemoryUsageSetting
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.pdmodel.graphics.image.PDImageXObject
import com.tom_roush.pdfbox.pdmodel.graphics.image.JPEGFactory
import com.tom_roush.pdfbox.text.PDFTextStripper
import java.io.File
import java.security.MessageDigest
import java.util.IdentityHashMap
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import org.json.JSONObject
import kotlin.math.*

data class Quality(val dpi:Int,val jpeg:Int)
data class QuickEstimate(val after:Long,val lower:Long,val upper:Long)
data class PdfResult(val file:File,val before:Long,val after:Long,val target:Long?,val attempts:Int) {
    val met:Boolean get() = target == null || after <= target
}

class PdfEngine(val context:Context) {
    val spec = JSONObject(context.assets.open("product.json").bufferedReader().readText())
    val qualities = listOf("HIGH","MEDIUM","LOW").associateWith {
        val p=spec.getJSONObject("qualities").getJSONObject(it); Quality(p.getInt("dpi"),p.getInt("jpeg_quality"))
    }
    private val cache=File(context.cacheDir,"pdf_candidates").apply{mkdirs()}
    init { PDFBoxResourceLoader.init(context) }
    private fun load(f:File):PDDocument = try { PDDocument.load(f,MemoryUsageSetting.setupTempFileOnly()) }
        catch(e:com.tom_roush.pdfbox.pdmodel.encryption.InvalidPasswordException) { throw IllegalArgumentException(spec.getJSONObject("errors").getString("encrypted"),e) }
    suspend fun quickEstimate(source:File,quality:String="MEDIUM",target:Long?=null):QuickEstimate {
        require(source.length()>0){"空文件"};require(target==null || target>0){"目标体积必须大于零"};currentCoroutineContext().ensureActive()
        val before=source.length();var imageBytes=0L;var weighted=0.0
        val start=System.nanoTime()
        load(source).use { doc ->
            require(!doc.isEncrypted){spec.getJSONObject("errors").getString("encrypted")};require(doc.numberOfPages>0){"PDF 没有页面"}
            for((i,obj) in doc.document.objects.withIndex()) {
                currentCoroutineContext().ensureActive()
                if(i>=256 || System.nanoTime()-start>350_000_000)break
                val st=obj.getObject() as? COSStream?:continue
                if(st.getCOSName(COSName.SUBTYPE)!=COSName.IMAGE)continue
                val length=max(0,st.getInt(COSName.LENGTH)).toLong()
                val factor=if(st.containsKey(COSName.SMASK)||st.containsKey(COSName.MASK)) .90 else {
                    val q=if(target==null)quality else "LOW"
                    val width=max(1,st.getInt(COSName.WIDTH));val height=max(1,st.getInt(COSName.HEIGHT))
                    val dpi=max(72.0,max(width,height)/11.7)
                    val area=min(1.0,(qualities.getValue(q).dpi/dpi).pow(2))
                    val jpeg=st.getDictionaryObject(COSName.FILTER).toString().contains("DCTDecode")
                    var codec=(if(jpeg)mapOf("HIGH" to .90,"MEDIUM" to .75,"LOW" to .58)else mapOf("HIGH" to .65,"MEDIUM" to .40,"LOW" to .25)).getValue(q)
                    if(jpeg && length.toDouble()/(width.toLong()*height)<.30)codec=.98
                    (area*codec).coerceIn(.03,.98)
                }
                imageBytes+=length;weighted+=length*factor
            }
        }
        imageBytes=min(before,imageBytes)
        var predicted=((before-imageBytes)*.93+weighted).roundToLong().coerceIn(1,before)
        if(target!=null)predicted=min(predicted,target)
        val spread=if(imageBytes>0).30 else .12
        return QuickEstimate(predicted,max(1,(predicted*(1-spread)).toLong()),min(min(before,target?:before),(predicted*(1+spread)).toLong()))
    }
    fun verify(f:File):List<List<Float>> = load(f).use { doc ->
        require(!doc.isEncrypted){spec.getJSONObject("errors").getString("encrypted")}
        require(doc.signatureDictionaries.isEmpty() && doc.signatureFields.isEmpty()){spec.getJSONObject("errors").getString("signed")}
        require(doc.numberOfPages>0){"PDF 没有页面"}
        doc.pages.map { p -> p.contents.use { input -> val buffer=ByteArray(8192);while(input.read(buffer)!=-1){} }; listOf(p.mediaBox.lowerLeftX,p.mediaBox.lowerLeftY,p.mediaBox.upperRightX,p.mediaBox.upperRightY) }
    }
    private class Placement:PDFStreamEngine() {
        val display=IdentityHashMap<COSStream,Pair<Float,Float>>()
        val images=IdentityHashMap<COSStream,PDImageXObject>()
        init { addOperator(Concatenate());addOperator(DrawObject());addOperator(SetGraphicsStateParameters());addOperator(Save());addOperator(Restore());addOperator(SetMatrix()) }
        override fun processOperator(operator:Operator, operands:MutableList<COSBase>) {
            if(operator.name=="Do" && operands.firstOrNull() is COSName) {
                val image=resources.getXObject(operands[0] as COSName)
                if(image is PDImageXObject) {
                    images[image.cosObject]=image
                    val m=graphicsState.currentTransformationMatrix
                    val old=display[image.cosObject]?:Pair(0f,0f)
                    display[image.cosObject]=Pair(max(old.first,abs(m.scalingFactorX)),max(old.second,abs(m.scalingFactorY)))
                }
            }
            super.processOperator(operator,operands)
        }
    }
    suspend fun compress(source:File, quality:String="MEDIUM", target:Long?=null,onProgress:(Int,Int)->Unit={_,_->}):PdfResult {
        currentCoroutineContext().ensureActive()
        require(source.length()>0){"空文件"};require(target==null || target>0){"目标体积必须大于零"}
        val boxes=verify(source)
        val digest=MessageDigest.getInstance("SHA-256").let { md ->source.inputStream().use { f->val b=ByteArray(1024*1024);while(true){val n=f.read(b);if(n<0)break;md.update(b,0,n)} };md.digest().joinToString(""){"%02x".format(it)} }
        val candidates=mutableListOf<File>()
        suspend fun candidate(p:Quality?) {
            currentCoroutineContext().ensureActive();onProgress(candidates.size+1,if(target==null)1 else 12)
            val out=File(cache,"${digest}_${p?.dpi}_${p?.jpeg}.pdf")
            if(!out.exists()) {
                val temp=File.createTempFile("candidate_",".pdf",cache)
                try {
                    load(source).use { doc ->
                        if(p!=null) {
                            val placements=Placement();for(page in doc.pages)placements.processPage(page)
                            for((stream,pt) in placements.display) {
                                currentCoroutineContext().ensureActive()
                                val image=placements.images.getValue(stream)
                                // Preserve masks, alpha, stencil images, ICC colour, custom decode and exotic codecs unchanged.
                                if(image.isStencil || stream.containsKey(COSName.SMASK) || stream.containsKey(COSName.MASK) || stream.containsKey(COSName.DECODE))continue
                                val cs=stream.getDictionaryObject(COSName.COLORSPACE)
                                if(cs!=COSName.DEVICERGB && cs!=COSName.DEVICEGRAY)continue
                                if(image.width.toLong()*image.height>24_000_000L)continue
                                val w=max(1,ceil(pt.first/72*p.dpi).toInt()).coerceAtMost(image.width)
                                val h=max(1,ceil(pt.second/72*p.dpi).toInt()).coerceAtMost(image.height)
                                val bitmap=image.image?:continue
                                var scaled:Bitmap?=null
                                try {
                                    val ratio=min(w.toDouble()/bitmap.width,h.toDouble()/bitmap.height).coerceAtMost(1.0)
                                    scaled=if(ratio<.85)Bitmap.createScaledBitmap(bitmap,max(1,(bitmap.width*ratio).roundToInt()),max(1,(bitmap.height*ratio).roundToInt()),true)else bitmap
                                    val replacement=JPEGFactory.createFromImage(doc,scaled,p.jpeg/100f)
                                    val newStream=replacement.cosObject
                                    val bytes=newStream.createRawInputStream().use{it.readBytes()}
                                    val oldSize=stream.createRawInputStream().use{ input ->var n=0L;val buf=ByteArray(8192);while(true){val k=input.read(buf);if(k<0)break;n+=k};n }
                                    if(bytes.size<oldSize) {
                                        stream.createRawOutputStream().use{it.write(bytes)}
                                        for(key in listOf(COSName.FILTER,COSName.COLORSPACE,COSName.BITS_PER_COMPONENT,COSName.WIDTH,COSName.HEIGHT)) stream.setItem(key,newStream.getItem(key))
                                        stream.removeItem(COSName.DECODE_PARMS)
                                    }
                                } finally { if(scaled!=null && scaled!==bitmap)scaled.recycle();bitmap.recycle() }
                            }
                        }
                        doc.save(temp)
                    }
                    require(verify(temp)==boxes){"页面完整性验证失败"}
                    if(temp.length()>source.length())source.copyTo(temp,true)
                    require(temp.renameTo(out)){"缓存写入失败"}
                } finally {temp.delete()}
            } else require(verify(out)==boxes){"缓存验证失败"}
            candidates+=out
        }
        if(target==null)candidate(qualities.getValue(quality)) else {
            candidate(null)
            if(candidates.last().length()>target) {
                val ladder=listOf(Quality(240,92),Quality(200,85),Quality(175,80),Quality(150,75),Quality(125,67),Quality(110,60),Quality(96,50),Quality(80,40),Quality(64,30),Quality(48,20),Quality(36,10))
                val measured=mutableMapOf<Int,Long>()
                suspend fun probe(index:Int):Long {
                    if(index !in measured){candidate(ladder[index]);measured[index]=candidates.last().length()}
                    return measured.getValue(index)
                }
                if(probe(3)<=target) {
                    for(adjacent in 2 downTo 0){if(probe(adjacent)>target)break}
                } else {
                    var lo:Int;var hi:Int
                    if(probe(6)<=target){lo=4;hi=5}else{lo=7;hi=ladder.lastIndex}
                    while(lo<=hi){val mid=(lo+hi+1)/2;if(probe(mid)<=target)hi=mid-1 else lo=mid+1}
                }
                val fitting=measured.filterValues{it<=target}.keys
                if(fitting.isNotEmpty()){val near=fitting.min()-1;if(near>=0)probe(near)}
                else if(ladder.lastIndex !in measured)probe(ladder.lastIndex)
            }
        }
        currentCoroutineContext().ensureActive()
        val fitting=candidates.filter{target!=null && it.length()<=target}
        val best=if(fitting.isNotEmpty())fitting.maxBy{it.length()}else candidates.minBy{it.length()}
        return PdfResult(best,source.length(),best.length(),target,candidates.size)
    }
    fun text(f:File):String=load(f).use{PDFTextStripper().getText(it)}
}
