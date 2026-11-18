package com.kedabao.pdfcompressor

import android.app.Application
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

data class Entry(val id:String,val uri:String,val name:String,val source:File,val original:Long,
    val estimates:Map<String,Long> = emptyMap(),val quality:String="GLOBAL",val selected:Boolean=true,
    val ranges:Map<String,String> = emptyMap(),val status:String="已导入，请选择参数后点击预估尺寸",val progress:Float=0f,val output:String?=null,val success:Boolean=false)

class PdfModel(app:Application):AndroidViewModel(app) {
    val entries=mutableStateListOf<Entry>()
    var busy by mutableStateOf(false)
    var quality by mutableStateOf("MEDIUM")
    var targetMode by mutableStateOf(false)
    var amount by mutableStateOf("1")
    var unit by mutableStateOf("MB")
    var outputTree by mutableStateOf<String?>(null)
    var message by mutableStateOf("全部在本机处理 · 开发者：可达包")
    private val preferences=app.getSharedPreferences("usage",0)
    var showGuide by mutableStateOf(!preferences.getBoolean("guide_seen",false))
    var guideStep by mutableStateOf(0)
    fun openGuide(){guideStep=0;showGuide=true}
    fun closeGuide(){showGuide=false;preferences.edit().putBoolean("guide_seen",true).apply()}
    fun targetBytes():Long?=if(targetMode)((amount.toDoubleOrNull()?:0.0)*(if(unit=="KB")1024 else 1048576)).toLong()else null
    fun estimateKey(e:Entry)="${if(e.quality=="GLOBAL")quality else e.quality}_${targetBytes()?:0}"
    val canStart:Boolean get()=(!targetMode || (targetBytes()?:0)>0) && entries.any{it.selected} && entries.filter{it.selected}.all{it.estimates.containsKey(estimateKey(it))}
    private val context get()=getApplication<Application>()
    private val engine=PdfEngine(app)
    private val inbox=File(app.filesDir,"inbox").apply{mkdirs()}
    private val results=File(app.filesDir,"results").apply{mkdirs()}
    private val journal=File(app.filesDir,"queue.json")
    private var job:Job?=null
    init {
        runCatching {
            val saved=JSONObject(journal.readText());outputTree=saved.optString("tree").ifBlank{null}
            val array=saved.getJSONArray("entries")
            for(i in 0 until array.length()) {
                val e=array.getJSONObject(i);val source=File(inbox,e.getString("id")+".pdf")
                if(source.exists())entries+=Entry(e.getString("id"),e.getString("uri"),e.getString("name"),source,source.length(),status="上次会话已恢复，请重新预估",output=e.optString("output").ifBlank{null})
            }
            if(saved.optBoolean("running"))message="上次任务因进程中断而停止；原文件未修改，可重新开始"
        }
        // Candidates are regenerable; keep cache bounded between process launches.
        File(app.cacheDir,"pdf_candidates").listFiles()?.forEach{it.delete()}
    }
    private fun save() {
        runCatching {
            val array=JSONArray();entries.forEach{e->array.put(JSONObject().put("id",e.id).put("uri",e.uri).put("name",e.name).put("output",e.output?:""))}
            val tmp=File(context.filesDir,"queue.tmp");tmp.writeText(JSONObject().put("running",busy).put("tree",outputTree?:"").put("entries",array).toString());check(tmp.renameTo(journal))
        }.onFailure{Log.e("ZhangPingPDF","journal",it)}
    }
    private fun update(id:String,fn:(Entry)->Entry) {val i=entries.indexOfFirst{it.id==id};if(i>=0)entries[i]=fn(entries[i])}
    fun select(id:String){if(!busy)update(id){it.copy(selected=!it.selected)}}
    fun setEntryQuality(id:String,q:String){if(!busy)update(id){it.copy(quality=q)}}
    fun all(){if(!busy)entries.indices.forEach{entries[it]=entries[it].copy(selected=true)}}
    fun remove(id:String){if(!busy){entries.find{it.id==id}?.source?.delete();entries.removeAll{it.id==id};save()}}
    fun clear(){if(!busy)entries.toList().forEach{remove(it.id)}}
    fun directory(uri:Uri){outputTree=uri.toString();save()}
    fun add(uris:List<Uri>) {
        if(busy)return
        busy=true
        job=viewModelScope.launch {
            try {
                for(uri in uris) {
                    if(entries.any{it.uri==uri.toString()}){message="已跳过重复文件";continue}
                    val id=UUID.randomUUID().toString()
                    try {
                        val name=context.contentResolver.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{c->if(c.moveToFirst())c.getString(0)else null}?:"document.pdf"
                        val dest=File(inbox,"$id.pdf")
                        withContext(Dispatchers.IO){context.contentResolver.openInputStream(uri)!!.use{src->dest.outputStream().use{out->src.copyTo(out)}}}
                        entries+=Entry(id,uri.toString(),name,dest,dest.length());save()
                        message="导入完成，请选择参数后点击“预估尺寸”"
                    } catch(e:CancellationException){throw e} catch(e:Exception){message="添加失败：${e.message}";Log.e("ZhangPingPDF","add",e);File(inbox,"$id.pdf").delete()}
                }
            } finally {busy=false;save()}
        }
    }
    private suspend fun estimate(id:String) {
        val entry=entries.first{it.id==id}
        try {
            val key=estimateKey(entry);val target=targetBytes()
            require(target==null || target>0){"请输入有效目标体积"}
            update(id){it.copy(status="快速预估中…",success=false)}
            val r=withContext(Dispatchers.IO){engine.quickEstimate(entry.source,if(entry.quality=="GLOBAL")quality else entry.quality,target)}
            update(id){it.copy(estimates=it.estimates+(key to r.after),ranges=it.ranges+(key to "${formatSize(r.lower)}–${formatSize(r.upper)}"),status=if(target==null)"近似预估完成，仅供参考"else"目标内参考预览，实际能否达标待压缩验证",progress=0f)}
        } catch(e:CancellationException){update(id){it.copy(status="已取消")};throw e}
        catch(e:Exception){Log.e("ZhangPingPDF","estimate",e);update(id){it.copy(status="失败：${e.message}")}}
    }
    fun estimateAll(){if(!busy){busy=true;job=viewModelScope.launch{try{for(e in entries.filter{it.selected}.toList())estimate(e.id);message="快速预估完成，可点击开始压缩"}finally{busy=false;save()}}}}
    fun start() {
        if(busy || entries.none{it.selected})return
        if(!canStart){message="请先点击预估尺寸，预览当前参数的近似结果";return}
        val target=if(targetMode)((amount.toDoubleOrNull()?:0.0)*(if(unit=="KB")1024 else 1048576)).toLong()else null
        if(target!=null && target<=0){message="请输入有效目标体积";return}
        busy=true;save()
        job=viewModelScope.launch {
            try {
                for(e in entries.filter{it.selected}.toList()) {
                    ensureActive()
                    update(e.id){it.copy(status="压缩中…",progress=0f,success=false)}
                    try {
                        val r=withContext(Dispatchers.IO){engine.compress(e.source,if(e.quality=="GLOBAL")quality else e.quality,target){n,total->
                            viewModelScope.launch{update(e.id){it.copy(status="实际搜索 $n/$total",progress=.05f+.85f*(n-1)/total)}}
                        }}
                        if(!r.met){update(e.id){it.copy(status="未达标：最小 ${formatSize(r.after)} / 目标 ${formatSize(target!!)}，未保存",progress=1f)};continue}
                        val uri=withContext(Dispatchers.IO){publish(e,r)}
                        update(e.id){it.copy(status="成功：${formatSize(r.before)} → ${formatSize(r.after)}，减少 ${"%.1f".format((1-r.after.toDouble()/r.before)*100)}%",output=uri.toString(),success=true,progress=1f)}
                        save()
                    } catch(e:CancellationException){throw e} catch(ex:Exception){Log.e("ZhangPingPDF","compress",ex);update(e.id){it.copy(status="失败：${ex.message}",progress=0f)}}
                }
                message="批次完成"
            } catch(e:CancellationException){entries.indices.forEach{i->if(entries[i].selected && !entries[i].success)entries[i]=entries[i].copy(status="已取消")};message="已取消，原文件保持完整"}
            finally{busy=false;save()}
        }
    }
    private suspend fun publish(e:Entry,r:PdfResult):Uri {
        currentCoroutineContext().ensureActive();require(r.met && r.after<=r.before)
        val safe=e.name.replace(Regex("[\\\\/:*?\"<>|\\p{Cntrl}]"),"_").trim('.',' ').ifBlank{"document.pdf"}
        val name=safe.substringBeforeLast('.')+"_compressed.pdf"
        if(outputTree==null) {
            var dest=File(results,name);var n=1
            while(dest.exists())dest=File(results,name.removeSuffix(".pdf")+"_${n++}.pdf")
            val temp=File.createTempFile(".publish_",".pdf",results)
            try{r.file.copyTo(temp,true);engine.verify(temp);require(temp.length()<=r.before && (r.target==null || temp.length()<=r.target)){"实际输出超过体积上限，未保存"};currentCoroutineContext().ensureActive();check(temp.renameTo(dest)){"输出写入失败"}}finally{temp.delete()}
            return FileProvider.getUriForFile(context,"${context.packageName}.files",dest)
        }
        val tree=DocumentFile.fromTreeUri(context,Uri.parse(outputTree))?:error("输出目录不可用")
        require(tree.canWrite()){ "输出目录没有写入权限" }
        var unique=name;var n=1
        while(tree.findFile(unique)!=null)unique=name.removeSuffix(".pdf")+"_${n++}.pdf"
        // SAF cannot guarantee atomic rename. Only create new documents; never truncate an original URI.
        val out=tree.createFile("application/pdf",unique)?:error("无法创建输出文件")
        try {
            currentCoroutineContext().ensureActive()
            context.contentResolver.openOutputStream(out.uri,"w")!!.use{dst->r.file.inputStream().use{it.copyTo(dst)}}
            val check=File.createTempFile("verify_",".pdf",context.cacheDir)
            try {
                context.contentResolver.openInputStream(out.uri)!!.use{src->check.outputStream().use{src.copyTo(it)}}
                require(check.length()==r.after && (r.target==null || check.length()<=r.target)){"输出大小验证失败或超过目标上限"};require(engine.verify(check)==engine.verify(e.source)){"输出页面验证失败"}
            } finally{check.delete()}
            return out.uri
        } catch(t:Throwable){out.delete();throw t}
    }
    fun cancel(){job?.cancel()}
}

fun label(q:String)=when(q){"HIGH"->"高品质";"MEDIUM"->"中品质";"LOW"->"低品质";else->"跟随全局"}
fun formatSize(n:Long)=if(n>=1048576)"%.2f MB".format(n/1048576.0)else "%.1f KB".format(n/1024.0)

class MainActivity:ComponentActivity() {
    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme=lightColorScheme(primary=Color(0xff2476e5),background=Color(0xfff6f8fc),surface=Color.White)) {
                val model:PdfModel=viewModel()
                if(model.showGuide) {
                    val steps=listOf("添加 PDF" to "点击添加文件，使用系统文件选择器批量导入 PDF。导入后不会自动执行预估或压缩。",
                        "压缩设置" to "选择按品质或按体积压缩，设置品质等级或每份文件的目标大小及 KB/MB 单位。未选模式的输入框为灰色。",
                        "预览" to "点击预估尺寸，快速查看近似大小和参考范围。预估不执行完整压缩；更改参数后请重新预估。",
                        "开始压缩" to "确认预览及保存位置后点击开始压缩，查看进度。默认另存副本；实际输出会验证，未达到目标会明确提示。")
                    AlertDialog(onDismissRequest={model.closeGuide()},title={Text("四步完成 PDF 压缩")},
                        text={Column(verticalArrangement=Arrangement.spacedBy(16.dp)){Text("${model.guideStep+1} / 4  ${steps[model.guideStep].first}",color=MaterialTheme.colorScheme.primary,fontSize=20.sp);Text(steps[model.guideStep].second);Text("右上角“？”可随时重新打开引导",fontSize=12.sp,color=Color.Gray)}},
                        confirmButton={TextButton(onClick={if(model.guideStep==3)model.closeGuide()else model.guideStep++}){Text(if(model.guideStep==3)"完成，开始使用"else"下一步")}},
                        dismissButton={Row{if(model.guideStep>0)TextButton(onClick={model.guideStep--}){Text("上一步")};TextButton(onClick={model.closeGuide()}){Text("关闭")}}})
                }
                val picker=androidx.activity.compose.rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()){uris->
                    uris.forEach{runCatching{contentResolver.takePersistableUriPermission(it,Intent.FLAG_GRANT_READ_URI_PERMISSION)}};model.add(uris)
                }
                val dirPicker=androidx.activity.compose.rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()){uri->if(uri!=null){runCatching{contentResolver.takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)};model.directory(uri)}}
                fun open(uri:String,share:Boolean=false){runCatching{
                    val intent=if(share)Intent(Intent.ACTION_SEND).apply{type="application/pdf";putExtra(Intent.EXTRA_STREAM,Uri.parse(uri))}else Intent(Intent.ACTION_VIEW).setDataAndType(Uri.parse(uri),"application/pdf")
                    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);startActivity(Intent.createChooser(intent,if(share)"分享 PDF" else "打开 PDF"))
                }.onFailure{model.message="没有可用的 PDF 查看器"}}
                Surface(modifier=Modifier.fillMaxSize().systemBarsPadding()) {
                    Column(Modifier.fillMaxSize().padding(horizontal=16.dp)) {
                        Row(Modifier.fillMaxWidth().padding(top=14.dp),verticalAlignment=Alignment.CenterVertically){Text("张平PDF压缩器",fontSize=24.sp,modifier=Modifier.weight(1f));OutlinedButton(onClick={model.openGuide()},shape=CircleShape,border=BorderStroke(1.dp,Color(0xffc6d8f0)),colors=ButtonDefaults.outlinedButtonColors(containerColor=Color(0xfff0f6ff),contentColor=Color(0xff2476e5)),contentPadding=PaddingValues(0.dp),modifier=Modifier.size(32.dp)){Text("?",fontSize=20.sp)}}
                        Text("可达包 · 离线处理，保留文字与矢量",color=Color.Gray,fontSize=12.sp)
                        LazyColumn(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(vertical=16.dp)) {
                            item {Button(onClick={picker.launch(arrayOf("application/pdf"))},enabled=!model.busy,modifier=Modifier.fillMaxWidth()){Text("＋ 添加 PDF 文件")}}
                            if(model.entries.isEmpty())item{OutlinedCard(Modifier.fillMaxWidth()){Text("选择 PDF 开始批量压缩\n支持系统文件选择器 · 不上传文件",modifier=Modifier.padding(24.dp),color=Color.Gray)}}
                            if(model.entries.isNotEmpty())item{
                                Row{TextButton(onClick={model.all()},enabled=!model.busy){Text("全选")};TextButton(onClick={model.clear()},enabled=!model.busy){Text("清空")}}
                            }
                            items(model.entries,key={it.id}) {e->
                                OutlinedCard(Modifier.fillMaxWidth()) {Column(Modifier.padding(12.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) {
                                    Row{Checkbox(checked=e.selected,onCheckedChange={model.select(e.id)},enabled=!model.busy);Text("PDF  ${e.name}",modifier=Modifier.weight(1f).padding(top=12.dp))}
                                    Text("原始 ${formatSize(e.original)} · ${e.estimates[model.estimateKey(e)]?.let{"约 "+formatSize(it)+"（仅供参考）"}?:"待预估 / 参数改变后请重新预估"}",fontSize=13.sp)
                                    e.ranges[model.estimateKey(e)]?.let{Text("近似范围：$it",fontSize=11.sp,color=Color.Gray)}
                                    Choice(listOf("GLOBAL","HIGH","MEDIUM","LOW"),e.quality,{model.setEntryQuality(e.id,it)},!model.busy && !model.targetMode){label(it)}
                                    Text(e.status,color=if(e.success)Color(0xff168447)else if(e.status.startsWith("失败")||e.status.startsWith("未达标"))Color(0xffc8333e)else Color.Gray,fontSize=13.sp)
                                    if(model.busy)LinearProgressIndicator(progress={e.progress},modifier=Modifier.fillMaxWidth())
                                    Row{TextButton(onClick={open(e.uri)}){Text("打开")};TextButton(onClick={model.remove(e.id)},enabled=!model.busy){Text("移除")}}
                                    if(e.output!=null)Row{TextButton(onClick={open(e.output)}){Text("压缩后文件")};TextButton(onClick={open(e.output,true)}){Text("分享")}}
                                    if(e.output!=null)Text("保存位置：${e.output}",fontSize=10.sp,color=Color.Gray)
                                }}
                            }
                            item {OutlinedCard {Column(Modifier.fillMaxWidth().padding(14.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                                Text("压缩设置",fontSize=20.sp)
                                Row(Modifier.selectable(!model.targetMode,enabled=!model.busy){model.targetMode=false}){RadioButton(!model.targetMode,{model.targetMode=false},enabled=!model.busy,colors=RadioButtonDefaults.colors(unselectedColor=Color(0xff7187a6)));Text("按品质压缩",modifier=Modifier.padding(top=12.dp))}
                                Choice(listOf("HIGH","MEDIUM","LOW"),model.quality,{model.quality=it},!model.busy && !model.targetMode){label(it)}
                                Row(Modifier.selectable(model.targetMode,enabled=!model.busy){model.targetMode=true}){RadioButton(model.targetMode,{model.targetMode=true},enabled=!model.busy,colors=RadioButtonDefaults.colors(unselectedColor=Color(0xff7187a6)));Text("按体积压缩（每份文件）",modifier=Modifier.padding(top=12.dp))}
                                Row {OutlinedTextField(model.amount,{model.amount=it},label={Text("最大体积")},singleLine=true,enabled=!model.busy && model.targetMode,colors=OutlinedTextFieldDefaults.colors(disabledContainerColor=Color(0xffedf0f5),disabledTextColor=Color(0xff99a4b5)),modifier=Modifier.weight(1f));Spacer(Modifier.width(8.dp));Choice(listOf("KB","MB"),model.unit,{model.unit=it},!model.busy && model.targetMode){it}}
                                Text("保存方式：另存为副本",fontSize=14.sp)
                                Text("为保护原文件，Android SAF 版本不覆盖原文件。",fontSize=12.sp,color=Color.Gray)
                                Text("输出：${model.outputTree?:"应用专属目录（可打开和分享）"}",fontSize=12.sp)
                                OutlinedButton(onClick={dirPicker.launch(null)},enabled=!model.busy){Text("选择系统输出目录")}
                                val selected=model.entries.filter{it.selected};val total=selected.sumOf{it.original};val known=selected.isNotEmpty() && selected.all{it.estimates.containsKey(model.estimateKey(it))}
                                val estimated=selected.sumOf{it.estimates[model.estimateKey(it)]?:0L}
                                Text("已选 ${selected.size} / ${model.entries.size} 份 · 原始 ${formatSize(total)}\n近似总大小：${if(known)"约 "+formatSize(estimated)else"点击预估尺寸"} · 完成 ${model.entries.count{it.success}}",fontSize=13.sp)
                            }}}
                        }
                        Text(model.message,fontSize=11.sp,color=Color.Gray,modifier=Modifier.padding(vertical=6.dp))
                        if(model.busy)LinearProgressIndicator(progress={model.entries.filter{it.selected}.let{e->if(e.isEmpty())0f else e.sumOf{it.progress.toDouble()}.toFloat()/e.size}},modifier=Modifier.fillMaxWidth())
                        OutlinedButton(onClick={model.estimateAll()},enabled=!model.busy && model.entries.any{it.selected},modifier=Modifier.fillMaxWidth()){Text("预估尺寸")}
                        Button(onClick={if(model.busy)model.cancel()else model.start()},enabled=model.busy||model.canStart,modifier=Modifier.fillMaxWidth().padding(bottom=12.dp).height(50.dp)){Text(if(model.busy)"取消任务"else"开始压缩")}
                    }
                }
            }
        }
    }
}

@Composable fun Choice(options:List<String>,selected:String,onSelect:(String)->Unit,enabled:Boolean=true,text:(String)->String) {
    var expanded by remember{mutableStateOf(false)}
    Box {OutlinedButton(onClick={expanded=true},enabled=enabled,colors=ButtonDefaults.outlinedButtonColors(disabledContainerColor=Color(0xffedf0f5),disabledContentColor=Color(0xff99a4b5))){Text(text(selected)+" ▾")};DropdownMenu(expanded,{expanded=false}){options.forEach{q->DropdownMenuItem(text={Text(text(q))},onClick={onSelect(q);expanded=false})}}}
}
