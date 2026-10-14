# Make-Your-PDF-into-Booklet-with-Trim
This code tansfers unsplit/split pdfs into booklet with trim and trim mark. Language Chinese.

# 介绍
- 英文太难了用中文说...
- 如果有自制书的打算，尤其是打算手工精装，在完成内容之后需要排版以供后续打印和装订。为了节省生命以及节省一点钱，我选择写个代码平替一下...
- 这个代码功能是实现PDF转换成小册子的排版，以及加上边距和裁切线。
- 使用GPT编写，接下来让GPT来介绍一下这个简单小工具的内容。

# 需要准备
- Windows 已安装 Python 3.10 或更高版本。
- 已安装 cpdf 和 pdfcpu。

# 启动
方式 A：双击“运行BookletBatch.bat”。
方式 B：在 PowerShell 中进入程序所在文件夹后运行：
    python .\BookletBatch.py

# 操作模式
模式 1：原始 PDF
- 输入完整的 PDF 文件路径。
- 选择每册页数：4、8、12 或 16；直接回车默认为 16。
- 输出 split、booklet、final 三个文件夹。

模式 2：已经拆分好的 PDF
- 输入单个 PDF 文件路径，或者包含多个 PDF 文件的文件夹路径。
- 不再询问拆分页数。
- 输出 booklet、final 两个文件夹。

# 每步处理
1. cpdf 按每册指定页数拆分（仅模式 1）。
2. pdfcpu booklet 执行 2-up 拼版。
3. cpdf 设置 TrimBox。
4. pdfcpu 按原流程以 mm 为单位向外扩展 8 mm。
5. cpdf 添加裁切线。

# 注意
- 默认输出到源文件旁边的“文件名_booklet_output”目录。
- 如果输出目录已存在，程序会自动选择 _001、_002 等新目录，避免覆盖原结果。
- 中间临时文件在系统临时目录中处理，运行结束后自动清理。
- 首次使用建议用一份较短的 PDF 测试，并检查最终 PDF 的页序、页面尺寸、8 mm 边距和裁切线。
