# sec573_book_indexer
This python scripts builds indexes for SEC573 course material in preperation for a GIAC exam. This is a project maintained by all SEC573 alumni.  Contribute and make it better!

## WARNING: You are better off building your index manually. Doing so forces you to read the books which is MORE important than having an index. This should only supliment your manually built index, not replace it.

## WARNING: Do no share Intellectual property such as PDFs and other copyright protected material.

## How to use

Pass this script the path to a directory containing your SEC573 PDF. You are prompted for the password. It identifies all the pages for the python keyword.

```
pip install pypdf2
py .\build_index.py ./path_to_pdf
What is your pdf password? blabla
Processing: SEC573_1_J01_03.pdf
Processing: SEC573_2_J01_03.pdf
Processing: SEC573_3_J01_02.pdf
Processing: SEC573_4_J01_02.pdf
...
rdpcap: ['SEC573_3_J01_02.pdf:Page 83', 'SEC573_3_J01_02.pdf:Page 86', 'SEC573_3_J01_02.pdf:Page 94', 'SEC573_3_J01_02.pdf:Page 95']
wrpcap: ['SEC573_3_J01_02.pdf:Page 83']
sr: ['SEC573_3_J01_02.pdf:Page 86']
patch: ['SEC573_4_J01_02.pdf:Page 6']
repr: ['SEC573_4_J01_02.pdf:Page 11']
min: ['SEC573_4_J01_02.pdf:Page 74']
max: ['SEC573_5_J01_02.pdf:Page 16']
conf: ['SEC573_6_J01_01.pdf:Page 6']
```

## Contributing
Do you wish it was better?  Me too!  Make it better and do a pull request.  Don't know how?  Watch this:

https://www.youtube.com/live/1y4B3IiXsMQ



