RISC-V Checkpoint with rv8
===========

## 简介
本项目基于rv8模拟器实现了可在任意Linux平台运行的RISC-V进程切片
### 特点
* <b>快速生成切片：</b>开启生成切片后模拟时间仅为不开启的150%，保持了rv8的高性能
* <b>任意Linux平台：</b>我的系统调用重演机制和Checkpoint Loader使得切片可在任意Linux平台运行，包括真实的RISC-V处理器
* <b>支持切片压缩：</b>通过低成本的压缩即可将大部分切片大小降低至10%以下
* <b>支持SimPoint：</b>可以生成SimPoint所需的BBV以供SimPoint分析

## 快速上手

### 编译所需程序
（这一部分如有疑问请见[rv8 README - Getting Started](README.rv8.md#getting-started)）
* 环境配置
    ```bash
    $ apt update
    $ apt install autoconf automake autotools-dev curl libmpc-dev libmpfr-dev libgmp-dev gawk build-essential bison flex texinfo gperf libtool patchutils bc zlib1g-dev
    ```
* 编译安装RISC-V工具链
    * <b>注：</b>必须安装gnu工具链，elf可选
    * <b>注：</b>不建议使用`apt`自带的`riscv64-linux-gnu`包，在静态链接时可能会有问题
    ```bash
    $ git clone https://github.com/riscv/riscv-gnu-toolchain.git
    $ cd riscv-gnu-toolchain
    $ git submodule update --init --recursive
    $ ./configure --prefix=/opt/riscv/toolchain
    $ make        # elf toolchain
    $ make linux  # gnu toolchain
    ```
* 编译安装rv8
    ```bash
    $ export RISCV=/opt/riscv/toolchain
    $ git clone https://github.com/lshpku/rv8-riscv-ckpt.git
    $ cd rv8-riscv-ckpt
    $ git submodule update --init --recursive
    $ make
    $ make install  # see below
    ```
* <b>注：</b>rv8默认需要安装到`/usr/local/bin`才能使用，如果不希望安装，也可以通过配置环境变量完成
    ```bash
    $ export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$(realpath build/linux_x86_64/lib)
    $ export PATH=$PATH:$(realpath build/linux_x86_64/bin)
    ```
* 编译Ckeckpoint Loader（CL）
    ```bash
    $ make -C ckpt cl
    ```
* 检查安装
    ```bash
    $ rv-sim ckpt/cl
    # usage: ckpt/cl cfg_path dump_path
    ```

### 运行程序并生成切片
* 我提供了一个`example/foo.c`样例，该样例简单且含有多种系统调用，比较具有代表性
    ```bash
    $ cd example
    $ riscv64-unknown-linux-gnu-gcc -O3 -static foo.c -o foo
    ```
* 运行测试程序的同时生成切片
    ```bash
    $ rv-sim -C foo.log -V 5000000 -- foo
    # Task 1: Memory allocation
    # success
    # Task 2: List sorting
    # success
    # Task 3: Matrix inversion
    # success
    # Running time: 2.440910780s
    ```
* 查看生成的切片，包括每个切片的内存镜像（`.dump`）文件和一个总的`.log`文件
    * <b>注：</b>由于运行的不确定性，切片的名称可能有所不同
    ```bash
    $ ls
    # checkpoint_0000000000000000000_0000000000005118377.dump
    # checkpoint_0000000000005118378_0000000000010300886.dump
    # checkpoint_0000000000010300887_0000000000015703282.dump
    # ...
    # foo.log
    ```

### 处理系统调用
* 上述生成的切片只是保存了切片处的内存，还没有处理系统调用，需要在本步骤中插入系统调用重演代码
    * 我将处理系统调用与生成切片分离是为了解耦，因为每个切片的系统调用各自独立，放在模拟过程中会增加模拟时间，解耦后则可以并行处理
    * 而且系统调用处理需要多次调用RISC-V工具链，Python更适合这个任务
* 使用Python脚本处理上述切片
    ```bash
    $ python3 ../ckpt/parse.py foo.log
    # checkpoint_0000000000000000000_0000000000005118377 first pass
    # checkpoint_0000000000000000000_0000000000005118377 rerunning
    # checkpoint_0000000000000000000_0000000000005118377 second pass
    # checkpoint_0000000000000000000_0000000000005118377 done
    # ...
    ```
* 查看处理后的切片，此时每个`.dump`文件都有自己独立的`.cfg`文件
    * 处理过的切片会用`.1`、`.2`的后缀与未处理的切片区分，后缀与切片的断点类型（即上面的`pass`数）有关
    * <b>注：</b>若一个切片同时有`.1`和`.2`后缀的版本，则`.1`的只是中间结果，`.2`才是最终切片
    ```bash
    $ ls
    # checkpoint_0000000000000000000_0000000000005118377.1.cfg
    # checkpoint_0000000000000000000_0000000000005118377.1.dump
    # checkpoint_0000000000000000000_0000000000005118377.2.cfg
    # checkpoint_0000000000000000000_0000000000005118377.2.dump
    # ...
    ```
* <b>【新增】多进程支持：</b>由于解析完log后的工作是独立的，可以用多进程加快这部分的速度
    * 例如，以下命令使用8进程进行处理
    ```bash
    $ python3 ../ckpt/parse.py foo.log -j 8
    ```
* <i><b>【测试中】验证切片：</b>使用标准的spike模拟器验证切片是否能正常运行
    * spike和FPGA的表现基本相同，spike正常运行意味着FPGA应该也能正常运行，反之亦然
    * 在处理切片时加上`-v`（`--verify`）参数即可
    ```bash
    $ python3 ../ckpt/parse.py foo.log -v
    # checkpoint_0000000000000000000_0000000000005118377 first pass
    # checkpoint_0000000000000000000_0000000000005118377 rerunning
    # checkpoint_0000000000000000000_0000000000005118377 second pass
    # checkpoint_0000000000000000000_0000000000005118377 verifying
    # checkpoint_0000000000000000000_0000000000005118377 done
    # ...
    ```
</i>

### 运行切片
* 为了方便演示，这里仍然用rv8来运行切片，实际上可以用任何兼容Linux的平台运行
    * 如riscv-pk、gem5（SE模式）、运行Linux系统的RISC-V处理器等
* 使用`cl`加载其中一个切片
    ```bash
    $ rv-sim ../ckpt/cl checkpoint_0000000000084601651_0000000000090049920.2.{cfg,dump}
    # map cl to 0x60000000-0x60001fff
    # map mc to 0x60002000-0x60003fff
    # invoke cl
    # begin execution
    # finish
    # cycle 000000000053258c
    # instret 000000000053258b
    ```
* <b>注：</b>由于切片中的系统调用均已被替换为mock代码，故原程序往`stdout`的写不会生效；控制台只能看到`cl`的输出，看不到原程序的输出
* 为了确认切片运行的正确性，我提供了随机store监控，如果一切正确则不会报错，否则会看到如下信息
    ```bash
    $ rv-sim ckpt/cl xxx.{cfg,dump}
    # ...
    # store assertion failed
    ```


## 进阶使用

### 添加CSR性能计数器
* 性能计数器在`replay.h`和`replay.c`中定义
* `replay()`在执行开始时保存当前数值，在结束时再读一次，将两次的差值打印出来

### 压缩切片
* 由于进程空间的内容常常是稀疏的，所以用简单的LZ77算法就可以很好地压缩内存镜像
* 首先需要编译压缩算法的动态链接库
    ```bash
    $ cd ckpt
    $ make fastlz.so
    ```
* 压缩一个切片的示例如下
    ```bash
    $ cd example
    $ python3 ../ckpt/compress.py checkpoint_0000000000062808575_0000000000068256844.2.{cfg,dump}
    # compressed pages: 9/11
    # compression ratio: 72.3%
    ```
* 压缩后的切片会带上`.c`后缀，与未压缩的区分
    ```bash
    $ ls *.c.*
    # checkpoint_0000000000062808575_0000000000068256844.2.c.cfg
    # checkpoint_0000000000062808575_0000000000068256844.2.c.dump
    ```

### 使用verilator模拟器运行切片
* 在模拟器中使用并非我的设计初衷，因为在模拟器里完全有更好的做切片的方式，本小节介绍的只是一个临时方案
* 首先假设你已经通过Chipyard构建出了一个verilator模拟器，例如`simulator-MediumBoomConfig`
* 在verilator上我们需要riscv-pk来提供Linux用户环境，用下面的方法获取和编译pk：
    ```bash
    $ git clone https://github.com/riscv-software-src/riscv-pk.git
    $ cd riscv-pk
    $ mkdir build
    $ cd build
    $ ../configure --host=riscv64-unknown-elf
    $ make -j`nproc`
    ```
* 编译得到的`pk`可执行程序就位于当前目录（`riscv-pk/build`）下，你可以把它移动到一个顺手的地方
* 运行切片，当前5M大小的切片可能需要10-20分钟
    ```bash
    $ cd example
    $ /path/to/simulator-MediumBoomConfig /path/to/pk ../ckpt/cl \
        checkpoint_0000000000005118403_0000000000010300911.2.{cfg,dump}
    # This emulator compiled with JTAG Remote Bitbang client. To enable, use +jtag_rbb_enable=1.
    # Listening on port 34625
    # [UART] UART0 is here (stdin/stdout).
    # bbl loader
    # map cl to 0x60000000-0x60001fff
    # map mc to 0x60002000-0x60003fff
    # invoke cl
    # begin execution
    # finish
    # cycle 0000000000674497
    # instret 00000000004f181b
    ```

## SimPoint
SimPoint是一个可以大幅节省性能评测成本的技术。它首先选出程序的一部分有代表性的执行片段（切片），然后只对这些片段进行性能评测，最后根据数学模型估算出程序完整执行的性能。在数学模型建立得当、所选执行片段有代表性的情况下，SimPoint可以相当精确地估算出程序的性能。关于SimPoint的更多细节请见论文：[SimPoint 3.0: Faster and More Flexible Program Analysis](https://cseweb.ucsd.edu/~calder/papers/JILP-05-SimPoint3.pdf)。

由于SimPoint的算法已经有开源实现，我的rv8模拟器并不自己做SimPoint分析，只是提供SimPoint工具所需的信息。本节我将以`foo.c`为例介绍一整套SimPoint的流程，包括生成BBV、进行SimPoint分析和估算IPC。

### 编译SimPoint
* 自行下载[SimPoint 3.2](https://cseweb.ucsd.edu/~calder/simpoint/simpoint-3-0.htm)的代码，解压，进入目录
    ```bash
    $ tar xvzf SimPoint.3.2.tar.gz
    $ cd SimPoint.3.2
    ```
* 由于SimPoint的代码已经很古老了，现在的编译器会报错，所以需要做如下修改
    ```bash
    $ vim analysiscode/Makefile
    ```
    将第1行改为
    ```Makefile
    CPPFLAGS = -Wall -pedantic -pedantic-errors -O3 -std=c++98 -include cstdlib -include climits -include cstring -include iostream
    ```
    再将第23-24行注释掉
    ```Makefile
    #SimpointOptions.o:
    #    $(CXX)  -Wall -pedantic -pedantic-errors -o SimpointOptions.o -c SimpointOptions.cpp
    ```
* 然后就可以正常编译了
    ```bash
    $ make
    ```
* 编译得到的可执行文件为`bin/simpoint`

### 生成BBV文件
* 假设你在`example`目录中，并且已经按[运行程序并生成切片](#运行程序并生成切片)得到了`foo`的初步切片
* 在处理系统调用时，用`--exec`参数指定测试程序的路径（此处为`foo`）；这将允许`parser.py`识别程序的基本块，从而得到每个基本块执行的次数
    ```bash
    $ python3 ../ckpt/parse.py foo.log --exec foo
    ```
* 加上`--exec`后每段切片都会多出一个`.bb`文件，里面就是切片的基本块向量（BBV）
    ```bash
    $ ls *.bb
    # checkpoint_0000000000000000000_0000000000005118377.bb
    # checkpoint_0000000000005118378_0000000000010300886.bb
    # checkpoint_0000000000010300887_0000000000015703282.bb
    # ...
    ```
* SimPoint要求输入为单个`.bb`文件，所以先将这些`.bb`文件合并为一个；由于文件名是按序的，所以合并的内容也是按序的
    ```bash
    $ cat *.bb > compose.bb
    ```

### 进行SimPoint分析
* 使用SimPoint分析上一步得到的BBV
    * 出于测试的目的，这里设置最大聚类数（`-maxK`）为5，但对于大型程序这个值应该设置为30或更高
    ```bash
    $ /path/to/simpoint -loadFVFile compose.bb -maxK 5 \
        -saveSimpoints simpoints.txt \
        -saveSimpointWeights weights.txt
    # ...
    # Post-processing run 3 (k = 3)
    # Saving simpoints of all non-empty clusters to file 'simpoints.txt'
    # Saving weights of all non-empty clusters to file 'weights.txt'
    ```
* SimPoint有两个输出文件，其中`simpoints.txt`如下
    * 第1列是所选切片的序号，*从0开始计*；第2列是SimPoint内部算法的聚类编号，可以不用管
    * SimPoint输出的时候是按聚类编号排序的，所以导致切片序号没有顺序，需要用户适应
    ```text
    7 0
    4 1
    1 2
    ```
* `weights.txt`如下
    * 除了第1列变为切片的权重外，其他和`simpoints.txt`相同
    ```text
    0.722222 0
    0.111111 1
    0.166667 2
    ```
* <i><b>【测试中】</b>可以用一个脚本收集这些SimPoint切片，同时生成适用于FPGA的运行脚本
    ```bash
    $ python3 ../ckpt/collect-simpoints.py foo.log -d foo_simpoints
    # reading log
    # found 18 checkpoints
    # input simpoints (end with an empty line):
    # ...
    # generating run script
    ```
</i>

### 计算IPC
* 你可以按任何顺序运行这些SimPoint切片，只要记住每个切片和权重的对应关系即可
* 假设每个切片运行得到的`cycle`、`instret`和前面SimPoint输出的权重如下

    |  cycle  | instret  |  weight
    | --- | --- | ---
    | 6779925 | 5449097 | 0.722222
    | 11846459 | 10006447 | 0.111111
    | 6154603 | 5182791 | 0.166667

* 由SimPoint的原理可知，`weight`是对CPI的线性加权，所以我们先算出CPI
    <img src="https://latex.codecogs.com/gif.latex?%5Cdpi%7B300%7D%20%5Cfn_cm%20%5Ctiny%20CPI%3D%5Cfrac%7B6779925%7D%7B5449097%7D%5Ctimes0.722222&plus;%5Cfrac%7B11846459%7D%7B10006447%7D%5Ctimes0.111111&plus;%5Cfrac%7B6154603%7D%7B5182791%7D%5Ctimes0.166667%3D1.228070" height="37"/>

* 故 <img src="https://latex.codecogs.com/gif.latex?%5Cdpi%7B300%7D%20%5Cfn_cm%20%5Ctiny%20IPC%3D1/CPI%3D0.814" height="16"/>

### SPEC2006 SimPoint切片库
* 你可以在[Latest Release](https://github.com/lshpku/rv8-riscv-ckpt/releases/tag/v220526)获取一些预先制作好的SPEC2006 benchmark的SimPoint切片
* 文件的命名为`{benchmark}_{输入}-{切片大小}-{SimPoint切片数量}.tar.xz`
    * 例如`gcc_166-100M-25P.tar.xz`的意思是`403.gcc`程序的`166.i`输入，切片大小为100M条指令，共有25个SimPoint切片
* 为了方便在不同平台上做实验，一些benchmark的切片大小有10M和100M可选
    * 在FPGA上建议用100M的，这样性能数据更加准确
    * 在模拟器上可以用10M的，否则运行时间可能会比较长（10M：40min，100M：6h）
* 每个压缩包内还有一个用于FPGA的`run.sh`脚本，脚本的运行顺序和`weights.txt`的顺序是一致的
    * 如果你不是在FPGA上运行，可以自己修改一下脚本，只要保持切片的顺序即可

## 故障排查
#### 运行`ckpt/parse.py`时报`expected cl`异常
* <b>原因：</b>当前开的进程数太多，导致系统管道断开；代码本身没有错
* <b>解决方法：</b>重新运行`ckpt/parse.py`，注意不要加`--rebuild`（`-r`）参数，这样它会自动跳过已经处理过的切片，从上次错误的地方开始继续执行

#### 某个切片用rv-sim正常运行，但用spike/qemu/FPGA报错
* 报错内容为`store assertion failed`、`illegal instruction`等
* <b>原因：</b>虽然我已经把rv-sim的浮点全部换成spike的softfloat库了，但可能还是有不兼容的地方，导致浮点精度误差
* <b>解决方法：</b>通常只有很少的切片会出现这个问题，并且一个切片错误不影响其他切片，故可以跳过这个切片

#### 某个程序用spike/qemu/FPGA正常运行，但用rv-sim报错
* 已知gcc_s04有此问题，报错原因为`load sigsegv`
* **原因**：rv-sim的系统调用有很多未知的问题，比如栈溢出抹掉有用数据，
* <del><b>解决方法：</b>由于调试难度过高，我暂时不打算解决</del>


## 原理介绍
请见[Checkpoint原理介绍](ckpt/README.md)
