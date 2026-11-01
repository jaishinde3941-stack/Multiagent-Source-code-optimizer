// Category: Resource Leaks
// Error: Memory leak on early return

#include <iostream>

int process(int value) {
    int* buffer = new int[100];
    
    if (value < 0) {
        return -1;  // ERROR: Memory leak - buffer not freed on early return
    }
    
    buffer[0] = value;
    int result = buffer[0] * 2;
    
    delete[] buffer;
    return result;
}

int main() {
    int result = process(-5);
    std::cout << "Result: " << result << std::endl;
    
    return 0;
}
