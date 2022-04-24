RISC-V Checkpoint with rv8
===========

## 目标

* 基于主流模拟器开发一个工具，能够在模拟的同时生成进程切片

* 生成切片应当使用简单的命令行操作即可完成，例如
    ```bash
    $ qemu-riscv64 --enabel-checkpoint \
        --checkpoint-interval 10000000 \
        --output-prefix coremark_slice_ \
        coremark_rv64_static.exe
    ```

* 生成的切片应当是自执行的，每个切片都是一个可执行文件，且执行过程中会自动进行性能统计

* 生成的切片应当只包含这段切片中访问过的代码和数据，减小切片的大小，例如
    ```bash
    $ ls -lh coremark*
    drwxr-xr-x 1 root root  4.3M Apr 10 15:06 coremark_rv64_static.exe
    drwxr-xr-x 1 root root 12.1K Apr 12 19:48 coremark_slice_0-1000028.exe
    drwxr-xr-x 1 root root 16.7K Apr 12 19:49 coremark_slice_1000028-2000576.exe
    drwxr-xr-x 1 root root 10.4K Apr 12 19:50 coremark_slice_2000576-3000294.exe
    ...
    ```

* 生成切片的过程应当尽可能快，避免做多余的模拟和分析

* 该工具应当满足SimPoint的需求，未必是自己做SimPoint分析，但别的工具做出结果后要能照着切


## 简易上手
* 根据[rv8 README](README.rv8.md)编译rv8
* TODO


## 原理介绍
请见[Checkpoint原理介绍](ckpt/README.md)
