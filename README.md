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
* <i><b>【测试中】标准验证：</b>使用标准的spike模拟器验证，及时发现错误
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
* <b>注：</b>由于切片中的系统调用均已被替换为mock代码，原程序往`stdout`的写也不会生效，故只能看到`cl`的输出，看不到原程序的输出
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

### SimPoint
* <b>说明：</b>我并不自己做SimPoint分析，我只是生成SimPoint所需的`.bbv`文件
* 先自行编译[SimPoint 3.2](https://cseweb.ucsd.edu/~calder/simpoint/simpoint-3-0.htm)，注意用低版本的gcc或clang，或者自己修改头文件，否则会报找不到定义
* 在处理系统调用时，用`--exec`参数指定测试程序的路径（此处为`foo`），用于分析基本块
    ```bash
    $ python3 ../ckpt/parse.py foo.log --exec foo
    ```
* 加上`--exec`后每段切片都会多出一个`.bb`文件
    ```bash
    $ ls *.bb
    # checkpoint_0000000000000000000_0000000000005118377.bb
    # checkpoint_0000000000005118378_0000000000010300886.bb
    # checkpoint_0000000000010300887_0000000000015703282.bb
    # ...
    ```
* 先将这些`.bb`文件合并为一个，由于文件名是按序的，所以合并的内容也是按序的
    ```bash
    $ cat *.bb > compose.bb
    ```
* 使用`simpoint`处理
    ```bash
    $ simpoint -loadFVFile compose.bb -maxK 30 \
        -saveSimpoints simpoints.txt \
        -saveSimpointWeights weights.txt
    ```
* <i><b>【测试中】</b>若切片数量较多，可以用一个脚本收集`simpoint`选中的切片
    ```bash
    $ python3 ../ckpt/collect-simpoints.py foo.log
    # reading log
    # found 18 checkpoints
    # input simpoints (end with an empty line):
    # ...
    # compressing
    # copying checkpoints
    # generating run script
    ```
</i>


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
