## RISC-V进程切片

### 目标

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


### 需要记录的信息

* 动态执行指令流，用于提取必需代码
    ```json
    {"type": "inst", "pc": "101da", "inst": "641c"}
    {"type": "inst", "pc": "101e8", "inst": "3b1180ef"}
    ```

* 访存地址与数据，用于提取必需数据
    ```json
    {"type": "read", "addr": "fffffff8f0", "data": "0000000080002000"}
    {"type": "write", "addr": "fffffff7c0", "data": "ffff2750"}
    ```

* 系统调用，包括返回值和调用期间修改的内存，用于重演该调用
    ```json
    {"type": "syscall", "ret": "1", "writes": [
        {"addrs": "59ac8", "data": "22876610"},
        {"addrs": "59acc", "data": "228e2e20"}]}
    ```

* 每个切片开头处所有用户寄存器的值，用于初始化切片状态
    ```json
    {"type": "regs", "pc": "200708",
        "ints": ["0", "2006fc", "7ffffbf0", ..., "23d2b6", "1"],
        "fps": ["0", "0", "0", ..., "0", "0"]}
    ```


### 提取进程运行时信息
这里讨论几个主流RISC-V模拟器对提取上述信息的支持

#### gem5
* 使用gem5自带的`DPRINTF`获取
    ```bash
    $ build/RISCV/gem5.opt \
        --debug-flag=FmtTicksOff,SyscallBase,ExecEnable,ExecUser,ExecFaulting,ExecEffAddr,ExecResult \
        --debug-file=coremark.log \
        configs/example/se.py -c coremark_rv64_static.exe
    ```

* 输出还是比较全面的，但是一个大问题是没有记录系统调用对内存的修改
    ```bash
    $ cat m5out/coremark.log
    60855388500: system.cpu: 0x150a0    : c_jr ra                    :
    60855389000: system.cpu: 0x1390a    : c_li a0, 1                 :
    60855389500: system.cpu: 0x1390c    : c_ldsp a4, 8(sp)           :
    60855390500: system.cpu: 0x1390e    : ld a5, 0(s3)               :
    60855391500: system.cpu: 0x13912    : bne a4, a5, 68             :
    ...
    ```

* gem5主要有两种方式访问用户内存
    * `VPtr`：作为参数直接传递，是一个用户地址的指针
    * `PortProxy`：附在内存上下文中，代表整个内存模型，可根据地址访问

* gem5的内存模型太复杂了，即使是`AtomicCPU`也要用`PacketPtr`传来传去，估计性能不会好到哪里

#### qemu-user
* 编译`rv64`架构的`linux-user`模式的qemu
    ```bash
    $ cd qemu-6.1.1/
    $ mkdir -p build
    $ cd build/
    $ ../configure --target-list=riscv64-linux-user
    $ make -j`nproc`
    ```

* qemu的执行过程
    * `linux-user/main.c: main()`：启动
    * `linux-user/riscv/cpu_loop.c: cpu_loop()`：无限循环
    * `accel/tcg/cpu-exec.c: cpu_exec()`：执行用户程序
    * `linux-user/syscall.c: do_syscall()`：处理系统调用
    * `linux-user/uaccess.c: lock_user()/unlock_user()`
        * 检查一段用户内存的权限，并返回其在系统空间的指针
        * 在`linux-user`模式下，`host_addr`=`guest_addr`+`guest_base`
    * `linux-user/fd-trans.h: fd_trans_host_to_target_data()/fd_trans_target_to_host_addr()`
        * 处理特殊文件的读写操作，如`socket`等，我们应该不用管

* qemu的系统调用包装得不错，但对逐条指令trace支持不好

#### rv8
* rv8的用户模式（rv-sim）是类似gem5的解释执行，不过因为rv8模型简单，速度比gem5快不少
    * 以CoreMark为例，运行时间`x86:qemu:rv8:FPGA:gem5`=`0.24:1:20:35:1000`

* rv8自带非常详细的trace，如下所示，甚至因为太丰富可以删掉一些
    ```bash
    $ rv-sim -o -c coremark-rv64-static
    0000000000000000000 core-0   :0000000000010b18 (02e000ef) jal         ra, pc + 46        ra=0x10b1c
    0000000000000000001 core-0   :0000000000010b46 (0005e197) auipc       gp, pc + 385024    gp=0x6eb46
    0000000000000000002 core-0   :0000000000010b4a (5e218193) addi        gp, gp, 1506       gp=0x6f128
    0000000000000000003 core-0   :0000000000010b4e (8082    ) ret
    0000000000000000004 core-0   :0000000000010b1c (87aa    ) mv          a5, a0             a0=0x642dd2fdb960bf96, a5=0x642dd2fdb960bf96
    0000000000000000005 core-0   :0000000000010b1e (fffff517) auipc       a0, pc - 4096      a0=0xfb1e
    0000000000000000006 core-0   :0000000000010b22 (7e850513) addi        a0, a0, 2024       a0=0x10306
    ...
    ```

* rv8的系统调用非常暴力，不检查直接接上了主机的系统调用，如下所示；如果要监控系统调用需要改代码，不过不会很复杂，可以先支持有限的系统调用
    ```cpp
    template <typename P> void abi_sys_read(P &proc)
    {
        int ret = read(proc.ireg[rv_ireg_a0],
            (void*)(addr_t)proc.ireg[rv_ireg_a1], proc.ireg[rv_ireg_a2]);
        if (proc.log & proc_log_syscall) {
            printf("read(%ld,0x%lx,%ld) = %d\n",
                (long)proc.ireg[rv_ireg_a0], (long)proc.ireg[rv_ireg_a1],
                (long)proc.ireg[rv_ireg_a2], cvt_error(ret));
        }
        proc.ireg[rv_ireg_a0] = cvt_error(ret);
    }
    ```

* 我决定就用rv8了，另外我想直接把进程切片功能集成到模拟器里，不用输出，毕竟IO会大大减慢速度


### 生成切片

#### 如何存放代码和数据
* 由于我们面向的是静态链接的程序，所以内存的使用只在`heap`和`stack`，比较好管理
* 我打算直接把数据的位置在生成ELF时就静态确定了，运行时不用再调用`brk`和`mmap`

#### 如何开始执行
* 先恢复所有的寄存器，然后用`jal`跳到开头的指令
* `jal`不需要寄存器，所以可以在不干扰寄存器的情况下跳过去

#### 如何处理系统调用
* RISC-V使用`ecall`指令进行系统调用，这条指令不可压缩，故可将其替换成`jal`，跳转到系统调用重演代码
* `jal`的范围是1MB，虽然执行的代码有可能超过这个大小，但在一段切片里不会全部访问到，所以会有很多空洞，我就把重演代码放在这些空洞里，应该基本都会满足
    * 若重演代码较大，可以先用`jal`跳到一个近的地方，在这里再用`jalr`跳到真正的重演代码
* 重演代码入口处可用`a0`加载栈帧，因为我们并不关心系统调用号（即`a0`），可以直接覆盖

#### 如何退出
* 这确实是一个问题，因为不是在模拟器环境中，很难知道什么时候是第几条指令
* 假设我们希望切片包含`[0, N)`部分的动态指令，可以用以下方法设置断点
    * 首次系统调用：找到`[N, MAX)`内的首次系统调用，在重演代码中退出
    * 首次执行的指令：找到`[N, MAX)`内第一条不在`[0, N)`中的指令，将其替换为跳到退出函数的`jal`指令
    * 混合式：先找到`[0, N)`内最后一次系统调用（记为`S`），然后找到`[N, MAX)`中第一条不在`(S, N)`中的指令，在重演代码中将这条指令改写为退出指令
* 断点方法应该尽可能多实现，因为一个方法不能保证在所有情况下都能切到合适的位置


### 系统调用实现

* 系统调用使用短调用和长调用实现，如下图所示
    ```text
                                        +----------+
                    +-----------+       |          |
    +-------+  -->  |           |  -->  |          |
    |  jal  |       | near_call |       | far_call |
    +-------+  <--  |           |  <--  |          |
                    +-----------+       |          |
                                        +----------+
    ```

* 短调用：跳转范围为`[-512KiB, 512KiB)`，作为系统调用（`jal`）和长调用之间的跳板
    * 短调用破坏性地使用了`a0`，因为系统调用一定会修改`a0`
    * 短调用还需自行保存和恢复`sp`，否则没有足够的寄存器用来跳转，使用`sp`是因为基于`sp`的访存可以生成压缩指令
    * 下面提供了一个优化的短调用实现，由于代码很短，可以很容易找到空洞来放置
    ```bash
    near_call:
        lui     a0, %hi(rt_buf)
        sd      sp, %lo(rt_buf)(a0)     # save sp
        lui     a0, %hi(far_call)
        jalr    a0, a0, %lo(far_call)
        lui     sp, %hi(rt_buf)
        ld      sp, %lo(rt_buf)(sp)     # restore sp
        jal     x0, offset

    rt_buf:
        .dword  0
    ```

* 长调用：跳转范围任意，代码可以任意长，用于处理复杂的调用
    * 由于短调用已经破坏了`a0`，长调用返回前需设置好`a0`
    * 长调用使用`sp`加载返回地址，因为这是短调用跳转到这里之前唯一保存的寄存器
    * 下面是长调用开头和结尾必须的工作，除此之外中间部分可以任意实现
    ```bash
    far_call:
        la      sp, rt_stack
        sd      a0, -8(sp)      # save return address
        # (save frame)
        # (do something)
        # (restore frame)
        li      a0, 1           # set return value
        ld      sp, -8(sp)      # restore return address
        jalr    x0, sp, 0
    ```


### 支持的系统调用列表

| 系统调用 | 写内存 |
| --- | :-: |
| brk |
| uname | Y |
| readlinkat | Y |
| clock_gettime | Y |
| fstat | Y |
| read | Y |
| write |
