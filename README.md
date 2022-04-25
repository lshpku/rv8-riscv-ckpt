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

#### 编译rv8
* 根据[rv8 README](README.rv8.md)编译即可
* 我对rv8的修改保留了其原有的使用方法，故正常使用参考[rv8 README](README.rv8.md)即可

#### 准备测试样例
* 我提供了一个`hello.c`的样例，简单且含有多种系统调用，比较具有代表性
* 使用linux-gnu工具链编译
    ```bash
    $ riscv64-unknown-linux-gnu-gcc -O2 -static hello.c -o hello
    ```

#### 生成逐指令log
* 生成log的功能已经被我内置在rv8中，直接运行rv8即可得到log
    ```bash
    $ rv-sim hello
    # Hello, world!
    # Running time: 0.000347279s!
    ```
* 注：rv8对于linux-gnu工具链编译的程序的exit处理有一点问题，不影响中间过程的正确性，也与我的修改无关

* 生成的log如下所示，内容包括寄存器初值，所有取指、访存和系统调用
    ```bash
    $ cat a.log
    # ireg = 0 be12a41ea72ca373 ... 27506ffb48b0469
    # freg = 0 0 ... 0
    # fetch 10370 = 02e000ef
    # fetch 1039e = 0005d197
    # ...
    # fetch 1045e = fa22
    # store 7ffffee0 = 0bbd34009d1390dd
    # ...
    # syscall = 0
    # syswrite 7ffffd90 = 52 44 b3 00 00 00 00 00
    # syswrite 7ffffd98 = 79 a9 a9 38 00 00 00 00
    # ...
    ```

#### 生成内存镜像与内存映射配置文件
* 使用python脚本处理log以生成这两种文件
    ```bash
    $ python3 ckpt/parse.py a.log
    ```
* 内存镜像（.dump）文件是程序执行过程中访问过的页
    * 我只记录被访问过的页，这充分节约了保存空间
* 内存映射描述（.cfg）文件记录了内存镜像的每个部分到用户地址空间的映射
    * 这个文件和内存镜像是一一对应的，我把它分出来只是为了方便阅读

#### 编译Ckeckpoint Loader（CL）
* 我提供了make脚本以编译`cl`
    ```bash
    $ make -C ckpt cl
    ```

#### 运行
* 仍然使用rv8运行
    ```bash
    $ rv-sim ckpt/cl test.cfg test.dump
    # cl_size    = 208
    # mc_size    = 1600
    # total_size = 1808
    # alloc_size = 4096
    # map cl to 0x60000000
    # invoke cl
    ```
* 注：我使用重演处理系统调用，故`hello.c`的输出都不会有效果，只能看见`cl`在加载时的输出
* 我目前还没有提供一个方便地查看运行正确性的机制，可以简单通过运行结束时dump寄存器值确认执行到了同一个位置
    ```bash
    $ rv-sim hello
    # instret  :              8463 time     :0x00685c57e73bdb6c
    # pc       :0x19cc2299c3ac56d6 fcsr     :0x00000000
    # ra       :0x0000000000014824
    # sp       :0x000000007ffffd20 gp       :0x000000000006d110
    # tp       :0x000000000006e780 t0       :0x000000000000000a
    # t1       :0x2525252525252525 t2       :0x0000000000000006
    # ...

    $ rv-sim ckpt/cl test.cfg test.dump
    # instret  :            112499 time     :0x00685befcfc4740a
    # pc       :0x1f31484b391d7852 fcsr     :0x00000000
    # ra       :0x0000000000014824
    # sp       :0x000000007ffffd20 gp       :0x000000000006d110
    # tp       :0x000000000006e780 t0       :0x000000000000000a
    # t1       :0x2525252525252525 t2       :0x0000000000000006
    # ...
    ```


## 原理介绍
请见[Checkpoint原理介绍](ckpt/README.md)
