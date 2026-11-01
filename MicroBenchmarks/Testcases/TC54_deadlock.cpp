// Category: Concurrency Errors
// Error: Deadlock potential

#include <iostream>
#include <thread>
#include <mutex>

std::mutex mutex1, mutex2;

void thread1Func() {
    mutex1.lock();
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    mutex2.lock();  // ERROR: Potential deadlock with thread2
    
    std::cout << "Thread 1 acquired both locks" << std::endl;
    
    mutex2.unlock();
    mutex1.unlock();
}

void thread2Func() {
    mutex2.lock();
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    mutex1.lock();  // ERROR: Different lock order - deadlock
    
    std::cout << "Thread 2 acquired both locks" << std::endl;
    
    mutex1.unlock();
    mutex2.unlock();
}

int main() {
    std::thread t1(thread1Func);
    std::thread t2(thread2Func);
    
    t1.join();
    t2.join();
    
    return 0;
}
