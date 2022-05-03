RISC-V Checkpoint with rv8
===========

## 目标

* 基于**主流模拟器**开发一个工具，能够在模拟的同时生成进程切片

* 生成切片应当使用简单的**命令行操作**即可完成

* 生成的切片应当是**自执行**的，不需要真实的系统调用，也不需要携带打开的文件

* 生成的切片应当**只包含**这段切片中访问过的代码和数据，减小切片的大小

* 生成切片的过程应当尽可能**快**，避免做多余的模拟和分析

* 该工具应当满足**SimPoint**的需求，未必是自己做SimPoint分析，但别的工具做出结果后要能照着切


## 简易上手

### 编译所需程序
#### 编译rv8
* 根据[rv8 README](README.rv8.md)编译本仓库提供的rv8
#### 编译测试程序
* 我提供了一个`hello.c`样例，该样例简单且含有多种系统调用，比较具有代表性
    ```bash
    $ riscv64-unknown-linux-gnu-gcc -O2 -static hello.c -o hello
    ```
#### 编译Ckeckpoint Loader（CL）
* `cl`是一个跨平台的用于加载切片的程序，相当于切片的Boot Loader
    ```bash
    $ make -C ckpt cl
    ```

### 生成切片的内存镜像
* 建立一个存放内存镜像的文件夹
    ```bash
    $ mkdir -p test
    ```
* 运行测试程序的同时生成内存镜像
    ```bash
    $ rv-sim -C test/test.log -V 1000000 -- hello
    # Hello, world!
    # #include <stdio
    # Running time: 0.000047264s!
    ```
* 查看生成的内存镜像文件，包括每个切片的`.dump`文件和一个总的`.log`文件
    ```bash
    $ ls test
    # checkpoint_0_100120690.dump
    # checkpoint_100120691_200605926.dump
    # checkpoint_200605927_300616537.dump
    # ...
    # test.log
    ```

### 处理内存镜像
* 上述生成的内存镜像只是将切片处的内存保存了下来，还没有处理系统调用，需要用Python脚本替换其中的系统调用
    * 我将系统调用处理的功能分离出来是为了解耦，因为每个切片的系统调用各自独立，放在模拟过程中会增加模拟时间，解耦后则可以并行处理
    * 而且系统调用处理需要多次调用RISC-V工具链，Python更适合这个任务
* 使用Python脚本处理上面得到的内存镜像
    ```bash
    $ python3 ckpt/parse.py test/test.log
    ```
* 查看处理后的内存镜像文件，此时每个`.dump`文件都有一个对应的的`.cfg`文件
    ```bash
    $ ls test
    # checkpoint_0_100120690.cfg
    # checkpoint_0_100120690.dump
    # checkpoint_100120691_200605926.cfg
    # checkpoint_100120691_200605926.dump
    # checkpoint_200605927_300616537.cfg
    # checkpoint_200605927_300616537.dump
    # ...
    ```
* **新增** 多进程支持：由于解析完log后的工作是独立的，可以用多进程加快这部分的速度
    * 例如，以下命令使用8进程进行处理
    ```bash
    $ python3 ckpt/parse.py -j 8 test/test.log
    ```

### 运行切片
* 为了方便演示，这里仍然用rv8来运行切片，实际上可以用任何兼容Linux的平台运行
    * 如riscv-pk、gem5（SE模式）、运行Linux系统的RISC-V处理器等
* 使用`cl`加载其中一个切片
    ```bash
    $ rv-sim ckpt/cl test/checkpoint_200605927_300616537.{cfg,dump}
    # cl_size    = 208
    # mc_size    = 1600
    # total_size = 1808
    # alloc_size = 4096
    # map cl to 0x60000000
    # invoke cl
    # ...
    ```
* 由于切片中的系统调用均已被替换为mock调用，原程序往`stdout`的写也不会生效，故只能看到`cl`的输出，看不到原程序的输出
* 为了确认切片运行的正确性，我提供了两种机制进行验证，即退出时寄存器状态和随机store监控
    * 如果一切正确则不会报错，否则会看到如下信息
    ```bash
    $ rv-sim ckpt/cl test/checkpoint_200605927_300616537.{cfg,dump}
    # ...
    # store assertion failed
    ```


## 进阶使用

### 添加CSR性能计数器
* 性能计数器在`replay.h`和`replay.c`中定义
* `replay()`在执行开始时保存当前数值，在结束时再读一次，将两次的差值打印出来

### SimPoint
* **新增** 支持输出[SimPoint 3.0](https://cseweb.ucsd.edu/~calder/simpoint/simpoint-3-0.htm)格式的BBV文件
* 先自行编译[SimPoint 3.0](https://cseweb.ucsd.edu/~calder/simpoint/simpoint-3-0.htm)，注意用低版本的gcc或clang，新版会报错
* 在处理内存镜像时，加上测试程序的路径（此处为`hello`），用于分析基本块
    ```bash
    $ python3 ckpt/parse.py --exec hello test/test.log
    ```
* 此时每段切片都会多出一个`.bb`文件
    ```bash
    $ ls test/*.bb
    # checkpoint_0000000000000000000_0000000000100033179.bb
    # checkpoint_0000000000100033180_0000000000200605926.bb
    # checkpoint_0000000000200605927_0000000000300615947.bb
    # ...
    ```
* 先将这些`.bb`文件合并为一个，由于文件名是按序的，所以合并的内容也是按序的
    ```bash
    $ cat test/*.bb > test/test.bb
    ```
* 使用`simpoint`处理
    ```bash
    $ simpoint -loadFVFile test/test.bb -maxK 30 \
        -saveSimpoints test/simpoints.txt \
        -saveSimpointWeights test/weights.txt
    ```
* 若切片数量较多，可以用一个脚本收集`simpoint`选中的切片
    ```bash
    $ python3 ckpt/collect.py test/test.log
    # found 803 checkpoints
    # input simpoint (end with an empty line):
    # ...
    # copying checkpoints
    # generating run script
    # compressing
    ```

### 开启预热
TODO

## 原理介绍
请见[Checkpoint原理介绍](ckpt/README.md)
